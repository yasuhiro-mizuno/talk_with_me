"""
voice_summary.md ファイル監視 + 自動読み上げサンプル

Cline がタスク完了時に voice_summary.md に1行サマリを書き出す。
このスクリプトはそのファイルの変更を監視し、内容を pyttsx3 で読み上げる。

実行: python sample_watcher.py
終了: Ctrl+C
"""

import os
import sys
import time
import pyttsx3

# ── 設定 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WATCH_FILE = os.path.join(SCRIPT_DIR, "voice_summary.md")
TTS_RATE = 150
POLL_INTERVAL = 1.0  # 秒


# ── 日本語音声検出 ──
def find_japanese_voice(engine):
    """日本語音声を探す"""
    for voice in engine.getProperty("voices"):
        vid = voice.id.lower()
        name = voice.name.lower()
        if "japanese" in vid or "japanese" in name:
            return voice
    return None


# ── 読み上げ (毎回エンジン再作成) ──
def speak_text(text: str, rate: int = TTS_RATE):
    """
    テキストを pyttsx3 で読み上げる。
    pyttsx3 はエンジンを使い回すと2回目以降で失敗することがあるため、
    毎回エンジンを作り直す。
    """
    engine = pyttsx3.init()
    jp = find_japanese_voice(engine)
    if jp:
        engine.setProperty("voice", jp.id)
    engine.setProperty("rate", rate)
    engine.say(text)
    engine.runAndWait()
    engine.stop()
    del engine


# ── ファイル監視 ──
def watch_and_speak():
    """voice_summary.md を監視し、変更されたら読み上げる"""

    print("=" * 50)
    print("voice_summary.md 監視 + 自動読み上げ")
    print("=" * 50)
    print(f"  監視対象: {WATCH_FILE}")
    print(f"  読み上げ速度: rate={TTS_RATE}")
    print(f"  ポーリング間隔: {POLL_INTERVAL}秒")
    print()
    print("  Cline がタスクを完了すると、")
    print("  voice_summary.md に書かれたサマリを読み上げます。")
    print()
    print("  終了: Ctrl+C")
    print("=" * 50)

    # 現在のファイル状態を記録
    last_mtime = 0.0
    last_content = ""

    if os.path.exists(WATCH_FILE):
        last_mtime = os.path.getmtime(WATCH_FILE)
        with open(WATCH_FILE, "r", encoding="utf-8") as f:
            last_content = f.read().strip()
        if last_content:
            print(f"\n  📄 既存の内容: 「{last_content}」")
            print(f"     (起動時は読み上げません。次の更新から読み上げます)")

    print("\n  🎤 監視中...\n")

    try:
        while True:
            time.sleep(POLL_INTERVAL)

            if not os.path.exists(WATCH_FILE):
                continue

            current_mtime = os.path.getmtime(WATCH_FILE)
            if current_mtime <= last_mtime:
                continue

            # ファイルが更新された
            last_mtime = current_mtime
            try:
                with open(WATCH_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
            except Exception as e:
                print(f"  ⚠ ファイル読み取りエラー: {e}")
                continue

            if not content or content == last_content:
                print(f"  (内容変更なし、スキップ)")
                continue

            last_content = content
            print(f"  🗣 読み上げ: 「{content}」")

            try:
                speak_text(content, TTS_RATE)
                print(f"  ✅ 完了\n  🎤 監視中...\n")
            except Exception as e:
                print(f"  ⚠ 読み上げエラー: {e}\n  🎤 監視中...\n")

    except KeyboardInterrupt:
        print("\n\n  終了します。")


if __name__ == "__main__":
    watch_and_speak()
