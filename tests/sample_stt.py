"""
マイク音声 → faster-whisper 文字起こし → voice_input.md に書き出し

常時マイクをリスニングし、音声区間を検出したら faster-whisper で文字起こし。
結果を voice_input.md に書き出す（sample_cline_input.py が拾って Cline に送信）。

初回起動時に faster-whisper の small モデル (~460MB) がダウンロードされます。

実行: python sample_stt.py
終了: Ctrl+C
"""

import os
import sys
import time
import wave
import struct
import tempfile
import numpy as np
import pyaudio
from faster_whisper import WhisperModel

# ── 設定 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "voice_input.md")

# マイク設定
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024  # フレーム数/チャンク
FORMAT = pyaudio.paInt16

# VAD 設定 (音量ベースの簡易 VAD)
SILENCE_THRESHOLD = 500   # この値以下を無音とみなす（環境に応じて調整）
SILENCE_DURATION = 1.5    # 発話後にこの秒数無音が続いたら発話終了とみなす
MIN_SPEECH_DURATION = 0.5 # 最低この秒数以上の発話があれば文字起こし

# Whisper 設定
MODEL_SIZE = "small"
LANGUAGE = "ja"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"


def get_rms(data: bytes) -> float:
    """音声データの RMS (Root Mean Square) を計算"""
    count = len(data) // 2  # 16bit = 2bytes
    shorts = struct.unpack(f"{count}h", data)
    sum_squares = sum(s * s for s in shorts)
    return (sum_squares / count) ** 0.5


def record_speech(pa: pyaudio.PyAudio, stream) -> bytes | None:
    """
    音声区間を検出して録音する。

    1. 音量が閾値を超えるまで待つ（発話開始待ち）
    2. 発話が始まったら録音
    3. 無音が SILENCE_DURATION 秒続いたら録音終了
    """
    frames = []
    is_speaking = False
    silence_start = None
    speech_start = None

    while True:
        try:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
        except Exception:
            continue

        rms = get_rms(data)

        if not is_speaking:
            if rms > SILENCE_THRESHOLD:
                # 発話開始
                is_speaking = True
                speech_start = time.time()
                silence_start = None
                frames.append(data)
        else:
            frames.append(data)

            if rms <= SILENCE_THRESHOLD:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start >= SILENCE_DURATION:
                    # 無音が続いた → 発話終了
                    speech_duration = time.time() - speech_start
                    if speech_duration >= MIN_SPEECH_DURATION:
                        return b"".join(frames)
                    else:
                        # 短すぎる → ノイズとして破棄
                        frames = []
                        is_speaking = False
                        silence_start = None
                        speech_start = None
            else:
                silence_start = None


def save_wav(audio_data: bytes, filepath: str):
    """PCM データを WAV ファイルとして保存"""
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_data)


def main():
    print("=" * 55)
    print("  マイク → faster-whisper → voice_input.md")
    print("=" * 55)
    print()

    # Whisper モデルをロード (初回はダウンロード)
    print(f"  📦 Whisper モデル '{MODEL_SIZE}' をロード中...")
    print(f"     (初回はダウンロードに数分かかります)")
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print(f"  ✅ モデルロード完了")
    print()

    # マイク初期化
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE,
    )
    print(f"  🎤 マイク起動 (rate={SAMPLE_RATE}, threshold={SILENCE_THRESHOLD})")
    print(f"  📝 出力先: {OUTPUT_FILE}")
    print(f"  終了: Ctrl+C")
    print()
    print(f"  🎤 聞いています... 話しかけてください\n")

    try:
        while True:
            # 音声区間を録音
            audio_data = record_speech(pa, stream)
            if audio_data is None:
                continue

            # 一時 WAV ファイルに保存
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
                save_wav(audio_data, tmp_path)

            try:
                # 文字起こし
                print("  ⏳ 文字起こし中...")
                segments, info = model.transcribe(
                    tmp_path,
                    language=LANGUAGE,
                    beam_size=5,
                    vad_filter=True,
                )
                text = "".join(seg.text for seg in segments).strip()
            finally:
                os.unlink(tmp_path)

            if not text:
                print("  (無音または認識不能、スキップ)")
                continue

            print(f"  📝 認識結果: 「{text}」")

            # voice_input.md に書き出し
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            print(f"  ✅ voice_input.md に書き出し完了")
            print(f"\n  🎤 聞いています...\n")

    except KeyboardInterrupt:
        print("\n\n  終了します。")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


if __name__ == "__main__":
    main()
