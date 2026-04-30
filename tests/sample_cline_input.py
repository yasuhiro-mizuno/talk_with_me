"""
voice_input.md 監視 → Cline チャットに自動送信

voice_input.md にテキストが書かれると、自動で VS Code の Cline チャット入力欄に
ペースト＆送信する。

問題点と対策:
  - VS Code 内で voice_input.md を編集するとカーソルがエディタに残る
  - 対策: 検知後にビープ音で通知 → 数秒の猶予 → 送信
  - 本番では STT が外部プロセスから書くためこの問題は起きない

実行: python sample_cline_input.py
終了: Ctrl+C
"""

import os
import sys
import time
import winsound
import pyperclip
import pyautogui
import pygetwindow as gw

# ── 設定 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WATCH_FILE = os.path.join(SCRIPT_DIR, "voice_input.md")
POLL_INTERVAL = 2.0  # ファイルチェック間隔（秒）
SEND_DELAY = 3.0     # 検知後、送信までの猶予（秒）— カーソルを移す時間

# pyautogui の安全設定
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2


def beep():
    """検知時にビープ音を鳴らす"""
    try:
        winsound.Beep(800, 300)
    except Exception:
        pass


def find_and_activate_vscode():
    """VS Code ウィンドウを見つけてアクティブにする"""
    windows = gw.getWindowsWithTitle("Visual Studio Code")
    if not windows:
        print("  ⚠ VS Code ウィンドウが見つかりません")
        return False

    win = windows[0]
    try:
        if win.isMinimized:
            win.restore()
        win.activate()
        time.sleep(0.5)
        print(f"  🪟 VS Code アクティブ化: {win.title[:60]}")
        return True
    except Exception as e:
        print(f"  ⚠ ウィンドウのアクティブ化に失敗: {e}")
        # フォールバック: Alt+Tab で試す
        try:
            pyautogui.hotkey("alt", "tab")
            time.sleep(0.5)
            return True
        except Exception:
            return False


def send_to_cline(text: str):
    """VS Code をアクティブにして Cline チャットにテキストを送信"""
    # 1. VS Code をアクティブにする
    print("  🔍 VS Code を探しています...")
    if not find_and_activate_vscode():
        return False

    # 2. クリップボードにコピー
    pyperclip.copy(text)
    print(f"  📋 クリップボードにコピー済み")

    # 3. Ctrl+V でペースト
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "v")
    print("  📝 ペースト実行")

    # 4. Enter で送信
    time.sleep(0.5)
    pyautogui.press("enter")
    print("  ⏎ Enter 送信")

    return True


def watch_and_send():
    """voice_input.md を監視し、変更されたら Cline に送信"""

    print("=" * 55)
    print("  voice_input.md 監視 → Cline 自動送信")
    print("=" * 55)
    print(f"  監視対象: {WATCH_FILE}")
    print(f"  チェック間隔: {POLL_INTERVAL}秒")
    print(f"  送信猶予: {SEND_DELAY}秒 (ビープ後にカーソルを移す時間)")
    print()
    print("  テスト手順:")
    print("  1. このスクリプトを起動")
    print("  2. voice_input.md にテキストを書いて保存")
    print("  3. ビープ音が鳴ったら Cline のチャット入力欄をクリック")
    print(f"  4. {SEND_DELAY}秒後に自動ペースト＆送信")
    print()
    print("  終了: Ctrl+C")
    print("=" * 55)

    last_mtime = 0.0
    last_content = ""

    if os.path.exists(WATCH_FILE):
        last_mtime = os.path.getmtime(WATCH_FILE)
        with open(WATCH_FILE, "r", encoding="utf-8") as f:
            last_content = f.read().strip()

    print("\n  🎤 監視中...\n")

    try:
        while True:
            time.sleep(POLL_INTERVAL)

            if not os.path.exists(WATCH_FILE):
                continue

            current_mtime = os.path.getmtime(WATCH_FILE)
            if current_mtime <= last_mtime:
                continue

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
            print(f"  🔔 変更検知: 「{content}」")
            beep()
            print(f"  ⏳ {SEND_DELAY}秒後に送信します — Cline のチャット入力欄をクリック！")
            time.sleep(SEND_DELAY)

            try:
                if send_to_cline(content):
                    print(f"  ✅ 送信完了\n  🎤 監視中...\n")
                else:
                    print(f"  ❌ 送信失敗\n  🎤 監視中...\n")
            except Exception as e:
                print(f"  ⚠ 送信エラー: {e}\n  🎤 監視中...\n")

    except KeyboardInterrupt:
        print("\n\n  終了します。")


if __name__ == "__main__":
    watch_and_send()
