"""
pyttsx3 TTS サンプル — 読み上げの雰囲気を確認するためのスクリプト

PLAN.md の Speaker 設計に沿った内容:
  - 日本語音声 (Haruka 等) を自動検出
  - rate 既定 180
  - 別スレッド + queue.Queue で非同期読み上げ (本番と同じ構成)
  - is_speaking フラグ

実行: python sample_tts.py
"""

import threading
import queue
import time
import pyttsx3


# ──────────────────────────────────────────────
# 1. 利用可能な音声の一覧表示 (情報確認用)
# ──────────────────────────────────────────────
def show_available_voices():
    """インストールされている全音声を表示する"""
    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    print("=" * 60)
    print("■ 利用可能な音声一覧")
    print("=" * 60)
    for i, voice in enumerate(voices):
        print(f"  [{i}] {voice.name}")
        print(f"      ID  : {voice.id}")
        print(f"      Lang: {voice.languages}")
        print()
    engine.stop()
    return voices


# ──────────────────────────────────────────────
# 2. 日本語音声の自動検出
# ──────────────────────────────────────────────
def find_japanese_voice(engine):
    """日本語音声を探して voice ID を返す。見つからなければ None"""
    voices = engine.getProperty("voices")
    for voice in voices:
        # Windows SAPI5 の場合、voice.id に "Japanese" や "ja" が含まれる
        vid_lower = voice.id.lower()
        name_lower = voice.name.lower()
        if "japanese" in vid_lower or "japanese" in name_lower or "ja-jp" in vid_lower:
            return voice
    return None


# ──────────────────────────────────────────────
# 3. シンプル版: 直接読み上げ
# ──────────────────────────────────────────────
def demo_simple():
    """最もシンプルな pyttsx3 読み上げ"""
    print("\n" + "=" * 60)
    print("■ デモ1: シンプル読み上げ")
    print("=" * 60)

    engine = pyttsx3.init()

    # 日本語音声を設定
    jp_voice = find_japanese_voice(engine)
    if jp_voice:
        engine.setProperty("voice", jp_voice.id)
        print(f"  日本語音声を検出: {jp_voice.name}")
    else:
        print("  ⚠ 日本語音声が見つかりませんでした。デフォルト音声を使用します。")

    # rate を 180 に設定 (PLAN.md の既定値)
    engine.setProperty("rate", 180)
    current_rate = engine.getProperty("rate")
    print(f"  読み上げ速度: {current_rate}")

    texts = [
        "こんにちは。pyttsx3のテストです。",
        "音声対話アプリ、トークウィズミーへようこそ。",
        "最近、何か気になっていることはありますか？",
    ]

    for text in texts:
        print(f"\n  🗣 読み上げ中: 「{text}」")
        engine.say(text)
        engine.runAndWait()
        print(f"  ✅ 完了")

    engine.stop()


# ──────────────────────────────────────────────
# 4. 別スレッド版: 本番に近い構成
# ──────────────────────────────────────────────
class Speaker:
    """
    PLAN.md の Speaker 設計を再現したクラス:
    - 別スレッドで pyttsx3 エンジン常駐
    - queue.Queue からテキストを受け取って読み上げ
    - is_speaking フラグで発話状態を公開
    """

    def __init__(self, rate: int = 180):
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._is_speaking = False
        self._rate = rate
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def speak(self, text: str):
        """読み上げキューにテキストを追加"""
        self._queue.put(text)

    def stop(self):
        """スレッドを終了させる"""
        self._queue.put(None)  # 終了シグナル
        self._thread.join(timeout=5)

    def _run(self):
        """別スレッドで実行される読み上げループ"""
        engine = pyttsx3.init()

        # 日本語音声を設定
        jp_voice = find_japanese_voice(engine)
        if jp_voice:
            engine.setProperty("voice", jp_voice.id)

        engine.setProperty("rate", self._rate)

        while True:
            text = self._queue.get()
            if text is None:
                break
            self._is_speaking = True
            engine.say(text)
            engine.runAndWait()
            self._is_speaking = False


def demo_threaded():
    """別スレッド版のデモ — メインスレッドは is_speaking を監視"""
    print("\n" + "=" * 60)
    print("■ デモ2: 別スレッド版 (本番に近い構成)")
    print("=" * 60)

    speaker = Speaker(rate=180)

    texts = [
        "これは別スレッドから読み上げています。",
        "メインスレッドでは、読み上げ中かどうかをフラグで確認できます。",
        "読み上げが終わると、フラグが自動的にオフになります。",
    ]

    for text in texts:
        speaker.speak(text)
        print(f"\n  🗣 キューに追加: 「{text}」")
        # is_speaking が True になるまで少し待つ
        time.sleep(0.3)
        while speaker.is_speaking:
            print(f"     ... is_speaking = True (読み上げ中)")
            time.sleep(1.0)
        print(f"  ✅ is_speaking = False (完了)")

    speaker.stop()
    print("\n  Speaker スレッド終了")


# ──────────────────────────────────────────────
# 5. 速度比較デモ
# ──────────────────────────────────────────────
def demo_rate_comparison():
    """読み上げ速度を変えて比較"""
    print("\n" + "=" * 60)
    print("■ デモ3: 読み上げ速度の比較")
    print("=" * 60)

    test_text = "読み上げ速度のテストです。この速さはいかがでしょうか。"

    for rate in [120, 150, 180, 220]:
        # pyttsx3 は rate 変更が反映されないことがあるため、毎回エンジンを再作成
        engine = pyttsx3.init()
        jp_voice = find_japanese_voice(engine)
        if jp_voice:
            engine.setProperty("voice", jp_voice.id)
        engine.setProperty("rate", rate)
        print(f"\n  🗣 rate={rate}: 「{test_text}」")
        engine.say(test_text)
        engine.runAndWait()
        engine.stop()
        del engine
        print(f"  ✅ 完了")


# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("pyttsx3 TTS サンプル")
    print("PLAN.md の Speaker 設計に基づいた動作確認\n")

    # 音声一覧を表示
    show_available_voices()

    # デモメニュー
    while True:
        print("\n" + "-" * 40)
        print("実行するデモを選んでください:")
        print("  1: シンプル読み上げ")
        print("  2: 別スレッド版 (本番に近い構成)")
        print("  3: 読み上げ速度の比較")
        print("  a: 全部実行")
        print("  q: 終了")
        print("-" * 40)

        choice = input(">>> ").strip().lower()

        if choice == "1":
            demo_simple()
        elif choice == "2":
            demo_threaded()
        elif choice == "3":
            demo_rate_comparison()
        elif choice == "a":
            demo_simple()
            demo_threaded()
            demo_rate_comparison()
        elif choice == "q":
            print("終了します。")
            break
        else:
            print("1, 2, 3, a, q のいずれかを入力してください。")
