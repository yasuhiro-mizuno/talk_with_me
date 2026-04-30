"""
LLM 補正テスト — ターミナルで対話して補正の動作を確認

STT の誤認識を想定したテキストを入力すると、
Claude が辞書＋コンテキストを使って補正した結果を表示します。

実行: python test_correction.py
"""
import os
from dotenv import load_dotenv
import anthropic

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

USER_DICT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_dict.md")
CORRECTION_MODEL = os.environ.get("CORRECTION_MODEL", "claude-3-5-haiku-latest")


def load_user_dict():
    if not os.path.exists(USER_DICT_FILE):
        return "(辞書なし)"
    with open(USER_DICT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    entries = [line.strip() for line in content.split("\n")
               if "→" in line and not line.strip().startswith("#")]
    return "\n".join(entries) if entries else "(辞書エントリなし)"


def correct(raw_text, history, user_dict):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")

    prompt = f"""あなたは音声認識(STT)の出力を補正するアシスタントです。
以下の音声認識結果を、文脈と辞書を参考にして正しい日本語に修正してください。

## ルール
- 誤認識された単語を正しい単語に置き換える
- 文の意味が通るように最小限の修正をする
- 元の意図を変えない
- 修正後のテキストのみを返す（説明不要）

## ユーザ辞書（よくある誤認識 → 正しい表記）
{user_dict}

## 直近の会話コンテキスト
{history if history else '(なし)'}

## 補正対象の音声認識結果
{raw_text}

## 補正後のテキスト（これだけを返してください）"""

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**client_kwargs)
    response = client.messages.create(
        model=CORRECTION_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def main():
    print("=" * 55)
    print("  LLM 補正テスト (対話モード)")
    print("=" * 55)
    print()

    user_dict = load_user_dict()
    print(f"  辞書エントリ数: {len([l for l in user_dict.split(chr(10)) if l.strip()])}")
    print(f"  補正モデル: {CORRECTION_MODEL}")
    print()
    print("  STT の誤認識を想定したテキストを入力してください。")
    print("  例: 「温泉入力のテストをしています」")
    print("  終了: q")
    print("=" * 55)

    history_lines = []

    while True:
        print()
        text = input("  入力 >>> ").strip()
        if text.lower() == "q":
            break
        if not text:
            continue

        try:
            history = "\n".join(history_lines[-10:])
            corrected = correct(text, history, user_dict)
            if corrected != text:
                print(f"  補正 >>> {corrected}")
            else:
                print(f"  補正 >>> (変更なし)")
            history_lines.append(f"ユーザ: {corrected}")
        except Exception as e:
            print(f"  エラー: {e}")

    print("  終了します。")


if __name__ == "__main__":
    main()
