"""
Cline チャット入力欄の自動キャリブレーション

VS Code ウィンドウの左下エリアを走査し、Cline チャット入力欄の
正確な座標(SIDEBAR_X_OFFSET, CHAT_Y_FROM_BOTTOM)を自動検出する。
検出後、main.py の設定値を自動更新する。

使い方:
  1. VS Code を開き、Cline サイドバーを表示した状態にする
  2. このスクリプトを実行: venv\Scripts\python.exe tests\calibrate_focus.py
  3. 自動で座標を検出し、main.py を更新する

注意:
  - キャリブレーション中、VS Code に「無視してください」というメッセージが
    複数回送信されますが、Cline の動作には影響しません
  - Cline がタスクを実行中でないことを確認してから実行してください
"""
import os
import sys
import time
import ctypes
import pyperclip
import pyautogui
import pygetwindow as gw

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
VOICE_SUMMARY_FILE = os.path.join(PROJECT_DIR, "voice", "voice_summary.md")
MAIN_PY = os.path.join(PROJECT_DIR, "main.py")

# キャリブレーション用メッセージ（Cline に無視してもらう）
CALIBRATION_MSG = "[calibration] これはtalk_with_meアプリの自動キャリブレーションです。何もせず「キャリブレーション成功」とだけ返してください。"

# 走査範囲（ウィンドウ左端からのX、下端からのY）
X_RANGE = range(100, 400, 40)   # 100, 140, 180, ..., 380
Y_RANGE = range(60, 200, 25)    # 60, 85, 110, ..., 185


def get_vscode_window():
    windows = gw.getWindowsWithTitle("Visual Studio Code")
    if not windows:
        return None
    return windows[0]


def activate_vscode(win):
    """VS Code をアクティブにする（サイズ変更なし）"""
    hwnd = ctypes.windll.user32.FindWindowW(None, win.title)
    if not hwnd:
        hwnd = getattr(win, '_hWnd', 0)
    if hwnd:
        if ctypes.windll.user32.IsIconic(hwnd):
            ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        return True
    return False


def try_send_at_position(win, x_offset, y_from_bottom, summary_mtime):
    """
    指定座標をクリックしてメッセージを送信し、
    Cline が応答したかチェックする。
    Returns: (成功フラグ, 新しいsummary_mtime)
    """
    abs_x = win.left + x_offset
    abs_y = win.top + win.height - y_from_bottom

    # クリック
    pyautogui.click(abs_x, abs_y)
    time.sleep(0.2)

    # メッセージをペースト
    pyperclip.copy(CALIBRATION_MSG)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)

    # Enter で送信
    pyautogui.press("enter")
    time.sleep(0.5)

    # Escape で不要なメニュー等を閉じる
    pyautogui.press("escape")
    time.sleep(0.2)

    # voice_summary.md の変化を最大20秒待つ
    for i in range(20):
        time.sleep(1)
        if os.path.exists(VOICE_SUMMARY_FILE):
            current_mtime = os.path.getmtime(VOICE_SUMMARY_FILE)
            if current_mtime > summary_mtime:
                return True, current_mtime
        # 経過表示
        if i % 5 == 4:
            print(".", end="", flush=True)

    return False, summary_mtime


def update_main_py(x_offset, y_from_bottom):
    """main.py の SIDEBAR_X_OFFSET と CHAT_Y_FROM_BOTTOM を更新"""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    content = re.sub(
        r'SIDEBAR_X_OFFSET\s*=\s*\d+',
        f'SIDEBAR_X_OFFSET = {x_offset}',
        content
    )
    content = re.sub(
        r'CHAT_Y_FROM_BOTTOM\s*=\s*\d+',
        f'CHAT_Y_FROM_BOTTOM = {y_from_bottom}',
        content
    )

    with open(MAIN_PY, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    print("=" * 60)
    print("  Cline チャット入力欄 自動キャリブレーション")
    print("=" * 60)
    print()

    # VS Code 確認
    win = get_vscode_window()
    if not win:
        print("  ❌ VS Code が見つかりません。VS Code を起動してください。")
        return

    print(f"  VS Code: {win.width}x{win.height} at ({win.left}, {win.top})")
    print()

    # voice ディレクトリ確認
    voice_dir = os.path.join(PROJECT_DIR, "voice")
    if not os.path.exists(voice_dir):
        os.makedirs(voice_dir)

    # 現在の voice_summary.md の状態を記録
    summary_mtime = 0.0
    if os.path.exists(VOICE_SUMMARY_FILE):
        summary_mtime = os.path.getmtime(VOICE_SUMMARY_FILE)

    # VS Code をアクティブに
    if not activate_vscode(win):
        print("  ❌ VS Code をアクティブにできません")
        return

    pyautogui.press("escape")
    time.sleep(0.3)

    # 走査パターン: 中心から外側へ（より早く見つかるように）
    # まず全候補を生成
    candidates = []
    for x in X_RANGE:
        for y in Y_RANGE:
            candidates.append((x, y))

    # 中心座標 (X=220, Y=110 付近が典型的)
    center_x, center_y = 220, 110
    candidates.sort(key=lambda p: abs(p[0] - center_x) + abs(p[1] - center_y))

    total = len(candidates)
    print(f"  🔍 {total} 箇所を走査します（中心から外側へ）")
    print(f"  ⏱  各位置で最大20秒待機します")
    print(f"  💡 Cline がアイドル状態であることを確認してください")
    print()

    found_x = None
    found_y = None

    for i, (x_offset, y_from_bottom) in enumerate(candidates):
        print(f"  [{i+1}/{total}] X={x_offset}, Y_from_bottom={y_from_bottom} ", end="", flush=True)

        # VS Code を再アクティブ（他の操作でフォーカスが移った場合）
        win = get_vscode_window()
        if not win:
            print("❌ VS Code 消失")
            return
        activate_vscode(win)
        time.sleep(0.3)

        success, summary_mtime = try_send_at_position(
            win, x_offset, y_from_bottom, summary_mtime
        )

        if success:
            print(" ✅ Cline に到達!")
            found_x = x_offset
            found_y = y_from_bottom
            break
        else:
            print(" -")

    print()

    if found_x is None:
        print("  ❌ Cline チャット入力欄を検出できませんでした")
        print("  💡 以下を確認してください:")
        print("     - Cline サイドバーが開いているか")
        print("     - Cline がアイドル状態か（タスク実行中でないか）")
        print("     - voice_output ルールが設定されているか")
        return

    print(f"  🎯 キャリブレーション成功!")
    print(f"     SIDEBAR_X_OFFSET  = {found_x}")
    print(f"     CHAT_Y_FROM_BOTTOM = {found_y}")
    print()

    # main.py を自動更新
    try:
        update_main_py(found_x, found_y)
        print(f"  ✅ main.py を自動更新しました")
        print(f"     アプリを再起動すると新しい座標が反映されます")
    except Exception as e:
        print(f"  ⚠ main.py の自動更新に失敗しました: {e}")
        print(f"     手動で以下の値を設定してください:")
        print(f"     SIDEBAR_X_OFFSET = {found_x}")
        print(f"     CHAT_Y_FROM_BOTTOM = {found_y}")


if __name__ == "__main__":
    main()
