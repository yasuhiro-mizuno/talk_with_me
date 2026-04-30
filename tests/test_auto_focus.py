"""
Cline チャットへの自動フォーカス テスト (v2)

VS Code ウィンドウ内の Cline チャット入力欄を直接クリックしてフォーカスする。
サイドバーの下部にある「Type a message...」入力欄の位置を推定してクリック。

実行: python test_auto_focus.py
"""

import time
import pyperclip
import pyautogui
import pygetwindow as gw

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

TEST_TEXT = "テスト: 自動フォーカスが成功しました"


def find_vscode_window():
    """VS Code ウィンドウを見つけて返す"""
    windows = gw.getWindowsWithTitle("Visual Studio Code")
    if not windows:
        print("  ⚠ VS Code が見つかりません")
        return None
    return windows[0]


def activate_and_focus_cline(win):
    """
    VS Code をアクティブにし、Cline のチャット入力欄をクリック。

    Cline サイドバーは VS Code の左側パネルにあり、
    チャット入力欄はそのパネルの最下部にある。
    ウィンドウの座標から相対位置を計算してクリックする。
    """
    # win32 API でウィンドウをアクティブにする（サイズを変えない）
    import ctypes
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, win.title)
        if not hwnd:
            hwnd = getattr(win, '_hWnd', 0)
        if hwnd:
            if ctypes.windll.user32.IsIconic(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # 最小化時のみ復元
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(0.5)
        else:
            print("  ⚠ ウィンドウハンドル取得失敗")
            return False
    except Exception as e:
        print(f"  ⚠ アクティブ化失敗: {e}")
        return False

    # ウィンドウの位置とサイズを取得
    left = win.left
    top = win.top
    width = win.width
    height = win.height
    print(f"  🪟 VS Code: left={left}, top={top}, width={width}, height={height}")

    # Cline のチャット入力欄の推定位置:
    # ── ここを調整してください ──
    # X: アクティビティバー(~48px) + サイドバー幅の半分(~170px)
    # Y: ウィンドウ下端から上方向のオフセット
    #    ステータスバー(~22px) + モデル表示(~25px) + ヒント行(~20px) + 入力欄中央(~15px) = ~82px
    SIDEBAR_X_OFFSET = 218   # 左端からのX距離
    CHAT_Y_FROM_BOTTOM = 115  # 下端からのY距離

    sidebar_center_x = left + SIDEBAR_X_OFFSET
    chat_input_y = top + height - CHAT_Y_FROM_BOTTOM

    print(f"  🎯 クリック位置: ({sidebar_center_x}, {chat_input_y})")

    # Escape を押して開いているダイアログを閉じる
    pyautogui.press("escape")
    time.sleep(0.3)

    # チャット入力欄をクリック
    pyautogui.click(sidebar_center_x, chat_input_y)
    time.sleep(0.5)

    return True


def test_auto_focus():
    """自動フォーカスのテスト"""
    print("=" * 55)
    print("  Cline 自動フォーカス テスト (v2 - クリック方式)")
    print("=" * 55)
    print()
    print(f"  テスト文: 「{TEST_TEXT}」")
    print(f"  3秒後に実行します...")
    print()

    time.sleep(3)

    win = find_vscode_window()
    if not win:
        return

    # Cline にフォーカス
    print("  Step 1: Cline チャット入力欄にフォーカス...")
    if not activate_and_focus_cline(win):
        return

    # テキストをペースト
    print("  Step 2: テキストをペースト...")
    pyperclip.copy(TEST_TEXT)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)

    # Enter で送信
    print("  Step 3: Enter で送信...")
    pyautogui.press("enter")
    time.sleep(0.3)

    print()
    print("  ✅ テスト完了!")
    print()
    print("  ⚠ 位置がずれた場合:")
    print("  コード内の sidebar_center_x / chat_input_y を調整してください")


if __name__ == "__main__":
    test_auto_focus()
