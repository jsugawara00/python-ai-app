# AI Writing Tool — AI ライティングツール

> Google Gemini API を使った 8 種類のライティング支援ツール。ブラウザで直接利用でき、生成結果を PDF / Word / Excel でダウンロード可能。

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-4285F4?style=flat&logo=google&logoColor=white)

---

## デモ

[hxat7he6exbsqd44sddv2h.streamlit.app](https://hxat7he6exbsqd44sddv2h.streamlit.app)

## 概要

サイドバーから 8 つのツールを切り替えて使う Streamlit シングルページアプリ。

| ツール | 概要 |
|--------|------|
| 📊 営業報告書作成 | 訪問・出張報告書を生成。PDF / Excel / Word 対応 |
| 📝 ブログ記事執筆 | テーマ・文体・文字数を指定して記事生成 |
| 📧 メール返信作成 | 受信メールから返信文を自動生成 |
| 📋 文章要約 | 長文を指定フォーマットで要約 |
| 📱 SNS投稿文作成 | 3パターンの投稿文を生成 |
| 🔍 文章校正・改善 | 誤字・表現を校正し改善点を解説 |
| 💡 タイトル・見出し生成 | 複数のタイトル案を生成 |
| 🌐 文章翻訳 | 多言語翻訳 |

## 技術スタック

| 項目 | 内容 |
|------|------|
| フレームワーク | Streamlit >= 1.28.0 |
| AI モデル | Google Gemini 3.5 Flash |
| PDF 生成 | reportlab（CIDフォント HeiseiKakuGo-W5） |
| Word 生成 | python-docx |
| Excel 生成 | openpyxl |
| 構成 | シングルファイル（`app.py`） |

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # GEMINI_API_KEY を設定
streamlit run app.py
```

API キーはサイドバーから直接入力することも可能です。

## ドキュメント

詳細な仕様・設計は [docs/SPEC.md](./docs/SPEC.md) を参照してください。
