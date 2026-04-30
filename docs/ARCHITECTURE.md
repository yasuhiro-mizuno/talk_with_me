# talk_with_me — アーキテクチャ詳細

## 全体構成

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐    ┌──────────────┐
│  Microphone  │───▶│  STT スレッド     │───▶│  LLM 補正     │───▶│  voice_input │
│  (PyAudio)   │    │  faster-whisper   │    │  (Claude)     │    │  .md         │
└──────────────┘    │  + ノイズ検出     │    │  辞書+文脈    │    └──────┬───────┘
                    └──────────────────┘    └──────────────┘           │
                                                                       ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────────────┐
│  Speaker     │◀───│  TTS スレッド     │◀───│  Cline 入力スレッド              │
│  (pyttsx3)   │    │  voice_summary   │    │  voice_input.md 監視             │
│  Haruka 150  │    │  .md 監視        │    │  → 自動フォーカス (座標クリック)  │
└──────────────┘    └──────────────────┘    │  → ペースト＆Enter               │
                                            └──────────────────────────────────┘
```

## スレッド構成 (main.py)

すべて `main.py` 1ファイルに統合。3つの daemon スレッドが並行動作する。

| スレッド | 関数 | 役割 |
|---------|------|------|
| **STT** | `stt_thread()` | マイク録音 → ノイズキャリブレーション → 発話検知 → faster-whisper 文字起こし → LLM 補正 → `voice_input.md` に書き出し |
| **Cline 入力** | `cline_input_thread()` | `voice_input.md` をポーリング監視 → VS Code アクティブ化 → Cline チャット欄クリック → ペースト → Enter |
| **Cline 出力** | `cline_output_thread()` | `voice_summary.md` をポーリング監視 → 変更検知 → pyttsx3 で読み上げ |

## ファイル構成

```
talk_with_me/
├── main.py              # 全機能統合 (STT + Cline入力 + Cline出力)
├── .env                 # API設定 (APIキー, ベースURL, モデル)
├── .env.example         # テンプレート
├── .clinerules/
│   └── voice_output.md  # Cline rule: タスク完了時にひらがなサマリを出力
├── voice_input.md       # STT → Cline への入力 (ランタイム)
├── voice_summary.md     # Cline → TTS への出力 (ランタイム)
├── tests/               # テスト・サンプルスクリプト (10個)
└── LOG/                 # 作業ログ
```

---

## STT 詳細

### 音声認識 (faster-whisper)
- モデル: `small` (CPU int8, ~460MB)
- 言語: `ja` 固定
- 重複セグメント除去: 連続する同一セグメントをフィルタ

### ノイズキャリブレーション
- 起動時に2秒間のノイズを自動測定
- `max(最大ノイズ × 1.5, 平均ノイズ × 2, 300)` で閾値を設定
- 環境に応じた閾値が自動で決まる

### 発話検知 (RMS ベース簡易 VAD)
- 閾値超えで発話開始
- 1.5秒の無音で発話終了
- 最大30秒の安全弁
- 0.5秒未満の発話はノイズとして破棄

---

## LLM 補正

STT の生テキストを Claude API で自動修正してから Cline に送る。

### 入力
- STT 生テキスト
- ユーザ辞書 (`user_dict.md` from グローバル rules)
- 直近5ターンの会話コンテキスト

### 処理
- `anthropic.Anthropic()` でクライアント生成（カスタムベースURL対応）
- モデル: `.env` の `CORRECTION_MODEL` (デフォルト: `claude-3-5-haiku-latest`)
- プロンプト: 辞書＋コンテキストを参照して誤認識を修正、修正テキストのみ返す
- API キー未設定時はスキップ（補正なしでそのまま送信）

### 会話履歴
- スレッドセーフな `_recent_history` リスト
- ユーザ発話と Cline サマリの直近10件を保持
- LLM 補正のコンテキストとして使用

---

## Cline 入力 (自動フォーカス)

### VS Code ウィンドウのアクティブ化
1. `pygetwindow` で "Visual Studio Code" ウィンドウを検索
2. `win32 API (SetForegroundWindow)` でアクティブ化（サイズ変更なし）
3. `IsIconic()` で最小化チェック → 最小化時のみ `SW_RESTORE`
4. マルチモニタ対応済み

### Cline チャット欄への送信
1. Escape で開いているダイアログを閉じる
2. ウィンドウ相対座標でチャット入力欄をクリック
   - `SIDEBAR_X_OFFSET = 218` (左端から)
   - `CHAT_Y_FROM_BOTTOM = 115` (下端から)
3. `pyperclip` でクリップボードにコピー → Ctrl+V → Enter
4. 送信後 `voice_input.md` をクリア

### 通知
- ビープ音 (800Hz, 300ms) で送信検知を通知

---

## Cline 出力 (読み上げ)

### ファイル監視
- `voice_summary.md` を1秒間隔でポーリング
- `os.path.getmtime()` で変更検知
- 内容が空または前回と同じならスキップ

### Cline rule (`.clinerules/voice_output.md`)
- Cline がタスク完了時に `voice_summary.md` にひらがなサマリを書き出す
- **全てひらがなで記述**（pyttsx3 の読み間違い防止）

### TTS (pyttsx3)
- 毎回エンジン再作成（使い回すと2回目以降で失敗する問題に対応）
- Haruka (ja-JP) 自動検出
- rate=150

---

## 外部連携

### Cline スキル: company-knowledge
- 場所: `~/.agents/skills/company-knowledge/`
- 未知の社内固有名詞が出た時に発火
- `knowledge_base.md` (スキル直下) に知見を追記
- グローバル `user_dict.md` に用語を自動登録

### グローバル rules
- `~/Documents/Cline/Rules/user_dict.md` — 社内用語辞書（Cline が常時参照）

---

## 設定一覧 (main.py 冒頭の定数)

| カテゴリ | 設定 | デフォルト | 説明 |
|---------|------|-----------|------|
| STT | `MODEL_SIZE` | `"small"` | Whisper モデル |
| STT | `SILENCE_DURATION` | `1.5` | 発話終了の無音秒数 |
| STT | `MAX_SPEECH_DURATION` | `30` | 最大録音秒数 |
| STT | `CALIBRATION_SECONDS` | `2` | ノイズ測定時間 |
| STT | `THRESHOLD_MULTIPLIER` | `1.5` | ノイズ閾値の倍率 |
| LLM | `CORRECTION_MODEL` | `.env` から | 補正用モデル |
| LLM | `CORRECTION_MAX_TOKENS` | `200` | 補正応答の最大トークン |
| LLM | `RECENT_HISTORY_COUNT` | `5` | 補正コンテキストのターン数 |
| TTS | `TTS_RATE` | `150` | 読み上げ速度 |
| Cline | `INPUT_POLL_INTERVAL` | `2.0` | voice_input 監視間隔(秒) |
| Cline | `OUTPUT_POLL_INTERVAL` | `1.0` | voice_summary 監視間隔(秒) |
| Cline | `SIDEBAR_X_OFFSET` | `218` | チャット欄のX座標 |
| Cline | `CHAT_Y_FROM_BOTTOM` | `115` | チャット欄のY座標 |
