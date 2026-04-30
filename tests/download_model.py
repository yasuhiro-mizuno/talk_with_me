"""Whisper small モデルを事前ダウンロード"""
from faster_whisper import WhisperModel
print("Whisper small モデルをダウンロード中...")
model = WhisperModel("small", device="cpu", compute_type="int8")
print("完了!")
