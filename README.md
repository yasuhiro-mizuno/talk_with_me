# talk_with_me — Cline 音声操作ブリッジ

## 概要

**Cline（VS Code のコーディングエージェント）を音声で操作する**ためのアプリケーションです。

マイクに話しかけると、音声がリアルタイムで文字起こしされ、Cline のチャットに自動送信されます。Cline がタスクを完了すると、結果サマリが音声で読み上げられます。キーボードを使わずに Cline と対話できます。

## 仕組み

```
🎤 マイクに話す
  → faster-whisper (STT) で文字起こし
  → Claude (LLM) で誤認識を自動補正
  → voice_input.md に保存
  → Cline チャット入力欄に自動ペースト＆送信
  → Cline が処理（ファイル編集、コマンド実行等）
  → voice_summary.md にサマリ出力 (Cline rule)
  → pyttsx3 (TTS) で読み上げ 🔊
```

## 技術スタック

| 機能 | 技術 | 備考 |
|------|------|------|
| 音声認識 (STT) | faster-whisper `small` + PyAudio + Silero VAD | ローカル・オフライン。CPU int8 推論 |
| 音声補正 | Anthropic Claude (Haiku) | ユーザ辞書＋会話コンテキストで誤認識を自動修正 |
| 音声読み上げ (TTS) | pyttsx3 (Windows SAPI5, Haruka) | オフライン、rate=150 |
| Cline 入力 | pyautogui + pygetwindow + win32 API | VS Code ウィンドウの座標クリックでチャット欄にペースト |
| Cline 出力 | ファイル監視 (voice_summary.md) | Cline rule で作業サマリを出力 → 監視して読み上げ |

## セットアップ

### 1. 仮想環境の作成

```
python -m venv venv
```

### 2. 依存パッケージのインストール

```
venv\Scripts\pip.exe install -r requirements.txt
```

### 3. .env ファイルの作成

`.env.example` をコピーして `.env` を作成し、API 設定を記入：

```
ANTHROPIC_API_KEY=あなたのAPIキー
ANTHROPIC_BASE_URL=https://your-endpoint-url（任意）
CORRECTION_MODEL=claude-haiku-4-5（任意、デフォルト: claude-3-5-haiku-latest）
```

### 4. Whisper モデルのダウンロード（初回のみ）

```
venv\Scripts\python.exe tests\download_model.py
```

約460MBのモデルがダウンロードされます。2回目以降はキャッシュから読み込まれます。

## 使い方

### アプリの起動

```
venv\Scripts\python.exe main.py
```

起動すると以下が自動で行われます：
1. 🔇 ノイズキャリブレーション（2秒間静かにする）
2. 📦 Whisper モデルのロード
3. 🎤 マイクの起動 → 常時リスニング開始

話しかけると：
1. 🔴 発話開始を検知
2. ⏹ 1.5秒の無音で発話終了を検知
3. ⏳ faster-whisper で文字起こし
4. ✨ Claude で誤認識を補正（辞書＋コンテキスト参照）
5. 🔔 ビープ音で通知
6. 📤 Cline チャットに自動送信
7. 🗣 Cline の完了サマリを読み上げ

### マイク ON/OFF 切り替え

**Ctrl+M**を押すと、マイク（音声認識）のON/OFFをいつでも切り替えられます。

- **マイク OFF**: 周囲の会議や独り言を拾わなくなる。TTS（読み上げ）は引き続き動作
- **マイク ON**: 音声認識を再開
- 音でフィードバック: 下降トーン（♪↓）= ミュート / 上昇トーン（♪↑）= アンミュート
- VS Code など他のアプリにフォーカスがあっても、グローバルに切り替え可能

### 設定の調整

`main.py` の冒頭にある定数で調整できます：

| 設定 | デフォルト | 説明 |
|------|-----------|------|
| `SILENCE_DURATION` | 1.5秒 | 発話終了と判定する無音時間 |
| `MAX_SPEECH_DURATION` | 600秒(10分) | 最大録音時間（安全弁） |
| `TTS_RATE` | 150 | 読み上げ速度 |
| `MIC_TOGGLE_HOTKEY` | Ctrl+M | マイクON/OFF切り替えのホットキー |
| `MIC_START_ENABLED` | True | 起動時のマイク状態（False=ミュート起動） |
| `SIDEBAR_X_OFFSET` | 218 | Cline チャット欄のX座標（左端から） |
| `CHAT_Y_FROM_BOTTOM` | 115 | Cline チャット欄のY座標（下端から） |

## ディレクトリ構成

```
talk_with_me/
├── main.py                # メインアプリケーション（1コマンドで全機能起動）
├── .env                   # API設定（gitignore対象）
├── .env.example           # API設定テンプレート
├── .clineignore           # Cline のアクセス制限（.env を保護）
├── .clinerules/
│   └── voice_output.md    # Cline rule: タスク完了時に音声サマリを出力
├── voice/                 # 音声関連ランタイムファイル
│   ├── voice_input.md     # STT → Cline への入力テキスト
│   ├── voice_draft.md     # 長文発話の下書き（10秒超、手動編集用）
│   └── voice_summary.md   # Cline → TTS への出力テキスト
├── docs/                  # ドキュメント
│   ├── CONCEPT.md         # アプリのコンセプト・ユースケース
│   └── ARCHITECTURE.md    # 詳細なアーキテクチャ・設定一覧
├── tests/                 # テスト・サンプルスクリプト
│   ├── sample_tts.py      # TTS 読み上げデモ（3種）
│   ├── sample_stt.py      # STT 単体テスト
│   ├── sample_watcher.py  # voice_summary 監視＋読み上げテスト
│   ├── sample_cline_input.py  # voice_input 監視＋Cline送信テスト
│   ├── test_auto_focus.py # Cline チャット欄の自動フォーカステスト
│   ├── test_llm.py        # LLM 接続テスト
│   ├── test_chat.py       # LLM チャットテスト（対話式）
│   ├── test_correction.py # LLM 補正テスト（対話式）
│   ├── calibrate_focus.py # Cline チャット欄の自動キャリブレーション
│   ├── test_sounds.py     # Windows サウンド試聴テスト
│   ├── check_voices.py    # 利用可能な音声一覧表示
│   └── download_model.py  # Whisper モデル事前ダウンロード
├── LOG/                   # 作業ログ
├── README.md              # このファイル
├── requirements.txt       # 依存パッケージ一覧
└── venv/                  # Python 仮想環境
```

## 関連する Cline 設定（アプリ外）

### グローバル rules
- `~/Documents/Cline/Rules/user_dict.md` — ユーザ辞書。Cline が常に参照する社内用語リスト

### スキル
- `~/.agents/skills/company-knowledge/` — 社内ナレッジ管理スキル。未知の固有名詞が出た時に発火し、知見ベースに追記＋用語を自動登録

## 対象環境

- **OS**: Windows 10/11
- **VS Code**: Cline 拡張がインストール済み
- **GPU**: 不要（CPU のみで動作）
- **マイク**: 必須
- **インターネット**: Claude API 通信＋初回モデルダウンロードに必要

### Cline チャット欄の自動キャリブレーション

サイドバーの幅を変えたり、別のPCで使う場合は、チャット入力欄の座標を再検出できます：

```
venv\Scripts\python.exe tests\calibrate_focus.py
```

VS Code の左下エリアを自動走査し、Cline チャット入力欄の座標を検出して `main.py` を自動更新します。

## 既知の制約

- Cline チャット欄へのフォーカスは座標クリック方式（自動キャリブレーションで検出可能）
- faster-whisper `small` の日本語認識は完璧ではないため、LLM 補正で補っている
- CPU 推論のため、長い発話は文字起こしに数秒かかる場合がある
- pyttsx3 の音声は機械的（将来 Edge-TTS への差替を検討可能）
