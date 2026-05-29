# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## セットアップ

```bash
pip install -r requirements.txt
```

`.env.example` をコピーして `.env` を作成し、Gemini APIキーを設定する：

```
GEMINI_API_KEY=your_gemini_api_key_here
```

## 起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が自動で開く。ファイル保存でホットリロードされる。

## アーキテクチャ

シングルファイル構成（`app.py`）の Streamlit アプリ。Google Gemini API を使った7種類のAIライティングツールを提供する。

### ルーティング

`TOOLS` 辞書がナビゲーションとページ関数を一元管理している。

```python
TOOLS = {
    "絵文字 ラベル": ("key", page_func),
    ...
}
```

サイドバーの `st.radio` で選択されたキーをもとに `page_func()` を呼び出す。**新しいツールを追加する際はここに登録するだけでナビゲーションに反映される。**

### AI呼び出し

`generate(prompt, temperature)` が唯一のAI呼び出し口。

- モデルは `gemini-3.5-flash` に固定（変更不可）
- `temperature` のデフォルトは `0.7`
- 校正・要約・翻訳など精度重視のツールは `temperature=0.3` を使う
- エラー時は例外をキャッチして日本語メッセージを返す（呼び出し元でのエラーハンドリングは不要）

### 初期化フロー

`configure_gemini()` が `main()` の先頭で一度だけ呼ばれ、APIキーの有無を検証する。戻り値 `is_configured`（bool）をサイドバーのステータス表示とページ上部の警告に使う。APIキー未設定でも画面は表示されるが、生成ボタン押下時にエラーメッセージが返る。

### スタイリング

カスタムCSSは `main()` 内の `st.markdown(..., unsafe_allow_html=True)` に集約する。サイドバーの幅は `min-width: 250px; max-width: 300px;` で固定済み。サイドバーのタイトルヘッダーはカスタムHTMLで実装されており、`st.title()` は使っていない。

## ツール一覧

| 関数 | 機能 |
|------|------|
| `page_blog` | ブログ記事執筆 |
| `page_email` | メール返信作成 |
| `page_summary` | 文章要約（temperature=0.3） |
| `page_sns` | SNS投稿文作成（3パターン生成） |
| `page_proofread` | 文章校正・改善（temperature=0.3） |
| `page_title` | タイトル・見出し生成 |
| `page_translate` | 文章翻訳（temperature=0.2） |

## 新しいツールの追加手順

1. `page_xxx()` 関数を実装する（他の `page_*` 関数を参考にする）
2. `TOOLS` 辞書に追加する：
   ```python
   "🎯 ツール名": ("key", page_xxx),
   ```
3. それだけでサイドバーに表示される

## 注意事項

- `st.session_state` はファイル保存によるホットリロードのたびにリセットされる
- 各 `page_*` 関数は独立しており、関数間で状態を共有しない設計になっている
- プロンプトは各 `page_*` 関数内にハードコードされている（外部ファイル化していない）
