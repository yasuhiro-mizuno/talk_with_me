"""LLM 接続テスト — .env の設定で Claude API に接続できるか確認"""
import os
from dotenv import load_dotenv
import anthropic

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

api_key = os.environ.get("ANTHROPIC_API_KEY")
base_url = os.environ.get("ANTHROPIC_BASE_URL")
model = os.environ.get("CORRECTION_MODEL", "claude-3-5-haiku-latest")

print("LLM 接続テスト")
print(f"  API Key: {'設定済み (' + api_key[:12] + '...)' if api_key else '未設定'}")
print(f"  Base URL: {base_url or '(デフォルト)'}")
print(f"  Model: {model}")
print()

if not api_key:
    print("ERROR: ANTHROPIC_API_KEY が .env に設定されていません")
    exit(1)

client_kwargs = {"api_key": api_key}
if base_url:
    client_kwargs["base_url"] = base_url

try:
    client = anthropic.Anthropic(**client_kwargs)
    response = client.messages.create(
        model=model,
        max_tokens=50,
        messages=[{"role": "user", "content": "テスト。「接続成功」とだけ返して。"}],
    )
    result = response.content[0].text.strip()
    print(f"  応答: {result}")
    print("\n  OK: LLM 接続成功!")
except Exception as e:
    print(f"\n  ERROR: {e}")
