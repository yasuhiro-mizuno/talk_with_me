"""利用可能な音声を確認する簡易スクリプト"""
import pyttsx3

engine = pyttsx3.init()
voices = engine.getProperty("voices")
print(f"利用可能な音声: {len(voices)} 件\n")
for i, voice in enumerate(voices):
    print(f"[{i}] {voice.name}")
    print(f"    ID  : {voice.id}")
    print(f"    Lang: {voice.languages}")
    # 日本語かどうか判定
    if "japanese" in voice.id.lower() or "japanese" in voice.name.lower():
        print(f"    >>> 日本語音声 <<<")
    print()
engine.stop()
