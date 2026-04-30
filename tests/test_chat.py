"""
LLM チャットテスト — ターミナルで Claude と直接会話

.env の設定が正しく動くか、対話形式で確認するためのスクリプト。

実行: python test_chat.py
終了: q
"""
import os
from dotenv import load_dotenv
import anthropic

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

MODEL = os.environ.get("CORRECTION_MODEL", "claude-3-5-haiku-latest")


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")

    print("=" * 55)
    print("  LLM チャットテスト")
    print("=" * 55)
    print(f"  Model: {MODEL}")
    print(f"  Base URL: {base_url or '(デフォルト)'}")
    print()
    print("  何でも話しかけてください。終了: q")
    print("=" * 55)

    if not api_key:
        print("\n  ERROR: .env に ANTHROPIC_API_KEY が未設定")
        return

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**client_kwargs)

    messages = []

    while True:
        print()
        user_input = input("  あなた >>> ").strip()
        if user_input.lower() == "q":
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=300,
                messages=messages,
            )
            reply = response.content[0].text.strip()
            messages.append({"role": "assistant", "content": reply})
            print(f"  Claude >>> {reply}")
        except Exception as e:
            print(f"  エラー >>> {e}")

    print("  終了します。")


if __name__ == "__main__":
    main()
