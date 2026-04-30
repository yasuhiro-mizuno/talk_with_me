"""
talk_with_me — Cline 音声操作ブリッジ (統合版)

1つのコマンドで全パイプラインを起動:
  - STT: マイク → faster-whisper → voice_input.md
  - Cline 入力: voice_input.md 監視 → Cline チャットにペースト＆送信
  - Cline 出力: voice_summary.md 監視 → pyttsx3 で読み上げ

実行: python main.py
終了: Ctrl+C
"""

import os
import sys
import time
import wave
import struct
import tempfile
import threading
import re
import logging
import winsound
import pyperclip
import pyautogui
import pygetwindow as gw
import pyaudio
import pyttsx3
import keyboard
from faster_whisper import WhisperModel
from dotenv import load_dotenv
import anthropic

# .env 読み込み
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── パス設定 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_INPUT_FILE = os.path.join(SCRIPT_DIR, "voice", "voice_input.md")
VOICE_DRAFT_FILE = os.path.join(SCRIPT_DIR, "voice", "voice_draft.md")
VOICE_SUMMARY_FILE = os.path.join(SCRIPT_DIR, "voice", "voice_summary.md")
USER_DICT_FILE = os.path.join(SCRIPT_DIR, "user_dict.md")
KNOWLEDGE_BASE_FILE = os.path.join(SCRIPT_DIR, "knowledge_base.md")

# ── STT 設定 ──
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16
SILENCE_THRESHOLD = None  # 起動時に自動キャリブレーション
SILENCE_DURATION = 1.5
MIN_SPEECH_DURATION = 0.5
MAX_SPEECH_DURATION = 600  # 最大録音秒数 (10分)
CONFIRMATION_THRESHOLD = 10.0  # この秒数を超えた発話はLLM補正後にユーザ承認を求める
CALIBRATION_SECONDS = 2   # キャリブレーション時間
THRESHOLD_MULTIPLIER = 1.5  # ノイズ × この倍率 = 閾値
MODEL_SIZE = "small"
LANGUAGE = "ja"

# ── LLM 補正設定 ──
CORRECTION_MODEL = os.environ.get("CORRECTION_MODEL", "claude-3-5-haiku-latest")
CORRECTION_MAX_TOKENS = 200
RECENT_HISTORY_COUNT = 5  # 直近N件の発話/応答を補正コンテキストに使う

# ── TTS 設定 ──
TTS_RATE = 150

# ── Cline 入力設定 ──
INPUT_POLL_INTERVAL = 2.0

# ── Cline 出力設定 ──
OUTPUT_POLL_INTERVAL = 1.0

# ── マイク ON/OFF 設定 ──
MIC_TOGGLE_HOTKEY = "ctrl+m"   # マイクON/OFF切り替えキー
MIC_START_ENABLED = True    # 起動時のマイク状態 (True=ON)

# ── pyautogui 安全設定 ──
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2

# ── マイク ON/OFF グローバル状態 ──
mic_enabled = threading.Event()
if MIC_START_ENABLED:
    mic_enabled.set()


def toggle_mic():
    """マイクのON/OFFを切り替える (グローバルホットキーから呼ばれる)"""
    if mic_enabled.is_set():
        mic_enabled.clear()
        print(f"\n  🔇 [マイク] OFF - 音声認識を一時停止しました ({MIC_TOGGLE_HOTKEY} で再開)")
        # 下降トーン = ミュート
        winsound.Beep(600, 150)
        winsound.Beep(400, 150)
    else:
        mic_enabled.set()
        print(f"\n  🎤 [マイク] ON - 音声認識を再開しました ({MIC_TOGGLE_HOTKEY} でミュート)")
        # 上昇トーン = アンミュート
        winsound.Beep(400, 150)
        winsound.Beep(600, 150)


# ════════════════════════════════════════
# TTS (読み上げ)
# ════════════════════════════════════════
def find_japanese_voice(engine):
    for voice in engine.getProperty("voices"):
        if "japanese" in voice.id.lower() or "japanese" in voice.name.lower():
            return voice
    return None


def speak_text(text: str):
    engine = pyttsx3.init()
    jp = find_japanese_voice(engine)
    if jp:
        engine.setProperty("voice", jp.id)
    engine.setProperty("rate", TTS_RATE)
    engine.say(text)
    engine.runAndWait()
    engine.stop()
    del engine


# ════════════════════════════════════════
# STT (音声認識)
# ════════════════════════════════════════
def get_rms(data: bytes) -> float:
    count = len(data) // 2
    shorts = struct.unpack(f"{count}h", data)
    return (sum(s * s for s in shorts) / count) ** 0.5


def calibrate_noise(stream, seconds: float = CALIBRATION_SECONDS) -> float:
    """背景ノイズを測定して閾値を返す"""
    print(f"  🔇 [STT] ノイズ測定中 ({seconds}秒)... 静かにしてください")
    rms_values = []
    chunks = int(SAMPLE_RATE / CHUNK_SIZE * seconds)
    for _ in range(chunks):
        try:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            rms_values.append(get_rms(data))
        except Exception:
            continue
    if not rms_values:
        return 500  # フォールバック
    avg_noise = sum(rms_values) / len(rms_values)
    max_noise = max(rms_values)
    threshold = max(max_noise * THRESHOLD_MULTIPLIER, avg_noise * 2, 300)
    print(f"  📊 [STT] ノイズ: 平均={avg_noise:.0f}, 最大={max_noise:.0f} → 閾値={threshold:.0f}")
    return threshold


def record_speech(stream, threshold: float) -> tuple[bytes, float] | None:
    """音声を録音し、(音声データ, 発話秒数) のタプルを返す
    マイクOFF時はバッファを読み捨てて待機する"""
    frames = []
    is_speaking = False
    silence_start = None
    speech_start = None
    was_muted = False  # ミュート→アンミュート復帰時のメッセージ制御用

    while True:
        # マイクOFFチェック: バッファを読み捨てて待機
        if not mic_enabled.is_set():
            try:
                stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                pass
            # 録音中にOFFになったら中断・破棄
            if is_speaking:
                print("  🔇 [STT] マイクOFF - 録音中断、データ破棄")
                frames, is_speaking, silence_start, speech_start = [], False, None, None
            was_muted = True
            time.sleep(0.05)
            continue

        # ミュート解除直後のメッセージ
        if was_muted:
            was_muted = False
            print(f"\n  🎤 聞いています...\n")

        try:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
        except Exception:
            continue
        rms = get_rms(data)
        if not is_speaking:
            if rms > threshold:
                is_speaking = True
                speech_start = time.time()
                silence_start = None
                frames.append(data)
                print(f"  🔴 [STT] 発話開始検知 (RMS={rms:.0f})")
        else:
            frames.append(data)
            # 最大録音時間チェック
            if time.time() - speech_start >= MAX_SPEECH_DURATION:
                duration = time.time() - speech_start
                print(f"  ⏰ [STT] 最大録音時間到達 ({MAX_SPEECH_DURATION}秒)")
                return (b"".join(frames), duration)
            if rms <= threshold:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start >= SILENCE_DURATION:
                    if time.time() - speech_start >= MIN_SPEECH_DURATION:
                        duration = time.time() - speech_start
                        print(f"  ⏹ [STT] 発話終了 ({duration:.1f}秒)")
                        return (b"".join(frames), duration)
                    frames, is_speaking, silence_start, speech_start = [], False, None, None
            else:
                silence_start = None


def save_wav(audio_data: bytes, filepath: str):
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_data)


# ════════════════════════════════════════
# LLM 補正 (STT 出力 → Claude で修正)
# ════════════════════════════════════════
# 直近の会話履歴 (補正コンテキスト用)
_recent_history: list[str] = []
_recent_history_lock = threading.Lock()


def add_to_history(role: str, text: str):
    """会話履歴に追加 (スレッドセーフ)"""
    with _recent_history_lock:
        _recent_history.append(f"{role}: {text}")
        while len(_recent_history) > RECENT_HISTORY_COUNT * 2:
            _recent_history.pop(0)


def get_recent_history() -> str:
    """直近の会話履歴を文字列で返す"""
    with _recent_history_lock:
        return "\n".join(_recent_history) if _recent_history else "(なし)"


def load_user_dict() -> str:
    """user_dict.md から辞書エントリを読み込む"""
    if not os.path.exists(USER_DICT_FILE):
        return "(辞書なし)"
    with open(USER_DICT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    # ``` ブロック内の「X → Y」行を抽出
    entries = []
    for line in content.split("\n"):
        line = line.strip()
        if "→" in line and not line.startswith("#"):
            entries.append(line)
    return "\n".join(entries) if entries else "(辞書エントリなし)"


def correct_stt_text(raw_text: str) -> str:
    """Claude API で STT 出力を補正する"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return raw_text  # API キー未設定時はそのまま返す

    user_dict = load_user_dict()
    recent = get_recent_history()

    prompt = f"""あなたは音声認識(STT)の出力を補正するアシスタントです。
以下の音声認識結果を、文脈と辞書を参考にして正しい日本語に修正してください。

## ルール
- 誤認識された単語を正しい単語に置き換える
- 文の意味が通るように最小限の修正をする
- 元の意図を変えない
- 修正後のテキストのみを返す（説明不要）
- 意味のないフィラー（「あ」「うー」「えーと」「あの」だけの発話など）の場合は「SKIP」とだけ返す

## ユーザ辞書（よくある誤認識 → 正しい表記）
{user_dict}

## 直近の会話コンテキスト
{recent}

## 補正対象の音声認識結果
{raw_text}

## 補正後のテキスト（これだけを返してください）"""

    try:
        # カスタムベースURL対応
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = anthropic.Anthropic(**client_kwargs)
        response = client.messages.create(
            model=CORRECTION_MODEL,
            max_tokens=CORRECTION_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        corrected = response.content[0].text.strip()
        return corrected if corrected else raw_text
    except Exception as e:
        print(f"  ⚠ [補正] LLM 補正失敗: {e}")
        return raw_text


def stt_thread(model: WhisperModel):
    """マイク → 文字起こし → voice_input.md"""
    pa = pyaudio.PyAudio()
    stream = pa.open(format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE,
                     input=True, frames_per_buffer=CHUNK_SIZE)

    # 自動キャリブレーション
    threshold = calibrate_noise(stream)
    print(f"  🎤 [STT] マイク起動 (閾値={threshold:.0f}) — 話しかけてください")
    try:
        while True:
            result = record_speech(stream, threshold)
            if result is None:
                continue
            audio_data, speech_duration = result

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
                save_wav(audio_data, tmp_path)
            try:
                print("  ⏳ [STT] 文字起こし中...")
                segments, _ = model.transcribe(tmp_path, language=LANGUAGE,
                                                beam_size=5, vad_filter=True)
                # 重複セグメント除去: 各セグメントを strip して空でないものだけ取得
                seg_texts = []
                for seg in segments:
                    s = seg.text.strip()
                    if s and (not seg_texts or s != seg_texts[-1]):
                        seg_texts.append(s)
                text = " ".join(seg_texts).strip()
            finally:
                os.unlink(tmp_path)
            if not text:
                print("  [STT] (認識不能、スキップ)")
                continue
            print(f"  📝 [STT] 認識(生): 「{text}」")

            # LLM で補正
            corrected = correct_stt_text(text)
            if corrected == "SKIP":
                print(f"  🚫 [補正] フィラー検知、スキップ")
                print(f"\n  🎤 聞いています...\n")
                continue
            if corrected != text:
                print(f"  ✨ [補正] 修正: 「{corrected}」")
            else:
                print(f"  ✨ [補正] 修正なし")

            # 長い発話は voice_draft.md に書き出し、自動送信しない
            # ユーザが VS Code で編集し、voice_input.md に手動で保存すれば送信される
            if speech_duration >= CONFIRMATION_THRESHOLD:
                winsound.Beep(600, 200)
                winsound.Beep(600, 200)
                with open(VOICE_DRAFT_FILE, "w", encoding="utf-8") as f:
                    f.write(corrected + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                print()
                print(f"  ⚠ [長文] 発話が{speech_duration:.1f}秒 (>{CONFIRMATION_THRESHOLD}秒) です。")
                print(f"  ⚠ [長文] voice_draft.md に書き出しました。自動送信しません。")
                print(f"  ┃ {corrected}")
                print(f"  ⚠ [長文] 送信するには voice_draft.md を編集後、voice_input.md に保存してください。")
                print(f"\n  🎤 聞いています...\n")
                add_to_history("ユーザ(下書き)", corrected)
                continue

            # 履歴に追加
            add_to_history("ユーザ", corrected)

            with open(VOICE_INPUT_FILE, "w", encoding="utf-8") as f:
                f.write(corrected + "\n")
                f.flush()
                os.fsync(f.fileno())
            print(f"  💾 [STT] voice_input.md 保存完了")
    except Exception as e:
        print(f"  ⚠ [STT] エラー: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


# ════════════════════════════════════════
# Cline 入力 (voice_input.md → Cline)
# ════════════════════════════════════════
# Cline チャット入力欄のクリック座標 (VS Code ウィンドウ相対)
SIDEBAR_X_OFFSET = 218   # 左端からのX距離
CHAT_Y_FROM_BOTTOM = 115  # 下端からのY距離


def focus_cline_chat():
    """VS Code をアクティブにし、Cline チャット入力欄を直接クリック"""
    import ctypes

    windows = gw.getWindowsWithTitle("Visual Studio Code")
    if not windows:
        print("  ⚠ [入力] VS Code が見つかりません")
        return False
    win = windows[0]

    # win32 API でウィンドウをアクティブにする（サイズを変えない）
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, win.title)
        if not hwnd:
            # タイトル完全一致で見つからない場合、pygetwindow の _hWnd を使う
            hwnd = getattr(win, '_hWnd', 0)
        if hwnd:
            if ctypes.windll.user32.IsIconic(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE (最小化時のみ)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
        else:
            return False
    except Exception:
        return False

    # Escape で開いているダイアログを閉じる
    pyautogui.press("escape")
    time.sleep(0.3)

    # Cline チャット入力欄をクリック (ウィンドウ座標を再取得)
    win = gw.getWindowsWithTitle("Visual Studio Code")[0]
    click_x = win.left + SIDEBAR_X_OFFSET
    click_y = win.top + win.height - CHAT_Y_FROM_BOTTOM
    pyautogui.click(click_x, click_y)
    time.sleep(0.5)
    return True


def cline_input_thread():
    """voice_input.md 監視 → Cline にペースト＆送信"""
    last_mtime = 0.0
    last_content = ""
    if os.path.exists(VOICE_INPUT_FILE):
        last_mtime = os.path.getmtime(VOICE_INPUT_FILE)
        with open(VOICE_INPUT_FILE, "r", encoding="utf-8") as f:
            last_content = f.read().strip()
    print("  📤 [入力] voice_input.md 監視中")
    while True:
        time.sleep(INPUT_POLL_INTERVAL)
        if not os.path.exists(VOICE_INPUT_FILE):
            continue
        current_mtime = os.path.getmtime(VOICE_INPUT_FILE)
        if current_mtime <= last_mtime:
            continue
        last_mtime = current_mtime
        try:
            with open(VOICE_INPUT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception:
            continue
        if not content or content == last_content:
            continue
        last_content = content
        print(f"  🔔 [入力] 検知: 「{content}」")
        winsound.Beep(800, 300)
        try:
            if focus_cline_chat():
                pyperclip.copy(content)
                time.sleep(0.3)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.5)
                pyautogui.press("enter")
                print("  ✅ [入力] Cline に送信完了")
                # 送信後に voice_input.md をクリア & last_content リセット
                with open(VOICE_INPUT_FILE, "w", encoding="utf-8") as f:
                    f.write("")
                last_content = ""
            else:
                print("  ❌ [入力] Cline チャット欄にフォーカスできません")
        except Exception as e:
            print(f"  ⚠ [入力] 送信エラー: {e}")


# ════════════════════════════════════════
# Cline 出力 (voice_summary.md → 読み上げ)
# ════════════════════════════════════════
def cline_output_thread():
    """voice_summary.md 監視 → 読み上げ"""
    last_mtime = 0.0
    last_content = ""
    if os.path.exists(VOICE_SUMMARY_FILE):
        last_mtime = os.path.getmtime(VOICE_SUMMARY_FILE)
        with open(VOICE_SUMMARY_FILE, "r", encoding="utf-8") as f:
            last_content = f.read().strip()
    print("  🔊 [出力] voice_summary.md 監視中")
    while True:
        time.sleep(OUTPUT_POLL_INTERVAL)
        if not os.path.exists(VOICE_SUMMARY_FILE):
            continue
        current_mtime = os.path.getmtime(VOICE_SUMMARY_FILE)
        if current_mtime <= last_mtime:
            continue
        last_mtime = current_mtime
        try:
            with open(VOICE_SUMMARY_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except Exception:
            continue
        if not content or content == last_content:
            continue
        last_content = content
        print(f"  🗣 [出力] 読み上げ: 「{content}」")
        add_to_history("Cline", content)
        try:
            # 読み上げ前に通知音（Windows チャイム音）
            winsound.PlaySound(r"C:\Windows\Media\chimes.wav", winsound.SND_FILENAME)
            time.sleep(0.5)
            speak_text(content)
            print("  ✅ [出力] 読み上げ完了")
        except Exception as e:
            print(f"  ⚠ [出力] 読み上げエラー: {e}")


# ════════════════════════════════════════
# メイン
# ════════════════════════════════════════
def main():
    print("=" * 55)
    print("  talk_with_me - Cline 音声操作ブリッジ")
    print("=" * 55)
    print()

    # グローバルホットキー登録 (マイクON/OFF)
    keyboard.add_hotkey(MIC_TOGGLE_HOTKEY, toggle_mic)
    print(f"  ⌨ [ホットキー] {MIC_TOGGLE_HOTKEY} = マイク ON/OFF 切り替え")
    mic_state = "ON" if mic_enabled.is_set() else "OFF"
    print(f"  🎤 [マイク] 初期状態: {mic_state}")
    print()

    # Whisper モデルロード
    print("  📦 Whisper モデルをロード中...")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    print("  ✅ モデルロード完了")
    print()

    # 各スレッドを起動
    threads = [
        threading.Thread(target=stt_thread, args=(model,), daemon=True, name="STT"),
        threading.Thread(target=cline_input_thread, daemon=True, name="ClineInput"),
        threading.Thread(target=cline_output_thread, daemon=True, name="ClineOutput"),
    ]
    for t in threads:
        t.start()

    print()
    print("  ✅ 全コンポーネント起動完了")
    print(f"  🎤 話しかけてください（{MIC_TOGGLE_HOTKEY}: マイクON/OFF, Ctrl+C: 終了）")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        keyboard.unhook_all()
        print("\n\n  終了します。")


if __name__ == "__main__":
    main()
