"""Windows システムサウンドの試聴テスト"""
import winsound
import time
import os

sounds = [
    ("1. SystemAsterisk", "SystemAsterisk", None),
    ("2. SystemDefault", "SystemDefault", None),
    ("3. SystemExclamation (現在の音)", "SystemExclamation", None),
    ("4. SystemHand", "SystemHand", None),
    ("5. Windows Notify.wav", None, r"C:\Windows\Media\Windows Notify.wav"),
    ("6. Windows Notify Calendar.wav", None, r"C:\Windows\Media\Windows Notify Calendar.wav"),
    ("7. chimes.wav", None, r"C:\Windows\Media\chimes.wav"),
    ("8. notify.wav", None, r"C:\Windows\Media\notify.wav"),
    ("9. Windows Ding.wav", None, r"C:\Windows\Media\Windows Ding.wav"),
    ("10. Windows Print complete.wav", None, r"C:\Windows\Media\Windows Print complete.wav"),
]

print("=" * 50)
print("  Windows サウンド試聴")
print("=" * 50)
print()

for name, alias, filepath in sounds:
    print(f"  {name} ...", end=" ", flush=True)
    try:
        if alias:
            winsound.PlaySound(alias, winsound.SND_ALIAS)
        elif filepath and os.path.exists(filepath):
            winsound.PlaySound(filepath, winsound.SND_FILENAME)
        else:
            print("(ファイルなし)")
            continue
        print("OK")
    except Exception as e:
        print(f"(エラー: {e})")
    time.sleep(1.5)

print()
print("  完了！好みの番号を教えてください。")
