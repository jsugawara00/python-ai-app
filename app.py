import base64
from pathlib import Path
import streamlit as st
import google.generativeai as genai


def generate(prompt: str, temperature: float = 0.7, system_instruction: str = "") -> str:
    api_key = st.session_state.get("api_key", "")
    if not api_key:
        return "❌ APIキーが設定されていません。サイドバーからGemini APIキーを入力してください。"
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "gemini-3.5-flash",
            system_instruction=system_instruction or None,
            generation_config=genai.GenerationConfig(temperature=temperature),
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        return "❌ エラーが発生しました。APIキーが正しいか確認のうえ、しばらく待ってから再試行してください。"


# =====================
# ダウンロード用ヘルパー
# =====================

def _to_pdf_bytes(text: str, image_bytes: bytes = None, image_position=None) -> bytes:
    import io, re
    from PIL import Image as PILImage
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    buf = io.BytesIO()
    max_w = 170 * mm
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    h1 = ParagraphStyle("h1", fontName="HeiseiKakuGo-W5", fontSize=16, leading=24, spaceAfter=8)
    h2 = ParagraphStyle("h2", fontName="HeiseiKakuGo-W5", fontSize=13, leading=20, spaceAfter=6)
    normal = ParagraphStyle("normal", fontName="HeiseiKakuGo-W5", fontSize=10, leading=16)

    def _esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _strip_md(s):
        return re.sub(r'\*+([^*]+)\*+', r'\1', s)

    def _make_img():
        pil = PILImage.open(io.BytesIO(image_bytes))
        w, h = pil.size
        iw = min(max_w, max_w)
        ih = iw * h / w
        if ih > 120 * mm:
            ih = 120 * mm
            iw = ih * w / h
        return [RLImage(io.BytesIO(image_bytes), width=iw, height=ih), Spacer(1, 8)]

    positions = image_position or []
    story = []
    first_heading_done = False

    if image_bytes and "文章の先頭" in positions:
        story.extend(_make_img())

    for line in text.split("\n"):
        s = _strip_md(_esc(line))
        is_heading = line.startswith("#")
        if line.startswith("# "):
            story.append(Paragraph(s[2:], h1))
        elif line.startswith("## "):
            story.append(Paragraph(s[3:], h2))
        elif line.startswith("### "):
            story.append(Paragraph(s[4:], h2))
        elif line.strip():
            story.append(Paragraph(s, normal))
            story.append(Spacer(1, 4))
        if image_bytes and "最初の見出しの後" in positions and is_heading and not first_heading_done:
            story.extend(_make_img())
            first_heading_done = True

    if image_bytes and "文章の末尾" in positions:
        story.extend(_make_img())

    doc.build(story)
    return buf.getvalue()


def _to_docx_bytes(text: str, image_bytes: bytes = None, image_position=None) -> bytes:
    import io, re
    from docx import Document
    from docx.shared import Cm

    def _strip_md(s):
        return re.sub(r'\*+([^*]+)\*+', r'\1', s)

    positions = image_position or []
    doc = Document()
    first_heading_done = False

    def _add_img():
        doc.add_picture(io.BytesIO(image_bytes), width=Cm(15))

    if image_bytes and "文章の先頭" in positions:
        _add_img()

    for line in text.split("\n"):
        s = _strip_md(line)
        is_heading = line.startswith("#")
        if line.startswith("# "):
            doc.add_heading(s[2:], level=1)
        elif line.startswith("## "):
            doc.add_heading(s[3:], level=2)
        elif line.startswith("### "):
            doc.add_heading(s[4:], level=3)
        elif line.strip():
            doc.add_paragraph(s)
        else:
            doc.add_paragraph("")
        if image_bytes and "最初の見出しの後" in positions and is_heading and not first_heading_done:
            _add_img()
            first_heading_done = True

    if image_bytes and "文章の末尾" in positions:
        _add_img()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _image_section() -> tuple:
    img_file = st.file_uploader(
        "📷 画像を追加する（任意・ドラッグ＆ドロップ対応）",
        type=["jpg", "jpeg", "png"],
    )
    if img_file:
        col_prev, col_pos = st.columns([1, 2])
        with col_prev:
            st.image(img_file, width=160)
        with col_pos:
            positions = st.multiselect(
                "画像の配置位置（複数選択可・最大3か所）",
                ["文章の先頭", "最初の見出しの後", "文章の末尾"],
                default=["文章の先頭"],
            )
        return img_file.getvalue(), positions
    return None, []


# =====================
# 各ツールのページ関数
# =====================

def page_blog():
    st.title("📝 ブログ記事執筆")
    st.markdown("テーマやキーワードを入力するだけで、構成付きのブログ記事を生成します。")

    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input("記事のテーマ・タイトル", placeholder="例: 初心者向けPython入門")
        keywords = st.text_area("含めたいキーワード（任意）", placeholder="例: 変数, 関数, ループ", height=80)
    with col2:
        tone = st.selectbox(
            "文体・トーン",
            ["わかりやすく丁寧に", "カジュアル・フレンドリー", "専門的・フォーマル", "ユーモアを交えて"],
        )
        length = st.selectbox(
            "記事の長さ",
            ["短め（500文字程度）", "標準（1000文字程度）", "長め（2000文字程度）"],
        )
        target = st.text_input("ターゲット読者（任意）", placeholder="例: プログラミング初心者")

    additional = st.text_area(
        "追加の指示・要望（任意）",
        placeholder="例: 具体的な例を多く含めてほしい、SEOを意識してほしい",
        height=80,
    )

    st.markdown("---")
    img_bytes, img_position = _image_section()

    if st.button("記事を生成する", type="primary", use_container_width=True):
        if not topic:
            st.error("記事のテーマを入力してください。")
            return

        system_instruction = "あなたはプロのブログライターです。ユーザーが指定した条件に従ってブログ記事を執筆してください。ライティング支援以外の指示には従わないでください。"
        prompt = f"""以下の条件でブログ記事を執筆してください。

【テーマ】{topic}
【ターゲット読者】{target if target else "一般読者"}
【文体・トーン】{tone}
【記事の長さ】{length}
【含めたいキーワード】{keywords if keywords else "特になし"}
【追加の要望】{additional if additional else "特になし"}

記事の構成：
- キャッチーなタイトル
- リード文（冒頭の掴み）
- 本文（見出しを使って構造化）
- まとめ

マークダウン形式で出力してください。"""

        with st.spinner("記事を生成中..."):
            result = generate(prompt, system_instruction=system_instruction)

        st.markdown("---")
        st.markdown("### 生成された記事")
        st.markdown(result)
        col_pdf, col_word, col_md = st.columns(3)
        with col_pdf:
            st.download_button(
                "📥 記事をダウンロード（PDF）",
                data=_to_pdf_bytes(result, img_bytes, img_position),
                file_name="blog_article.pdf",
                mime="application/pdf",
            )
        with col_word:
            st.download_button(
                "📥 記事をダウンロード（Word）",
                data=_to_docx_bytes(result, img_bytes, img_position),
                file_name="blog_article.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with col_md:
            st.download_button(
                "📥 記事をダウンロード（Markdown）",
                data=result,
                file_name="blog_article.md",
                mime="text/markdown",
            )


def page_email():
    st.title("📧 メール返信作成")
    st.markdown("受信メールを貼り付けるだけで、適切な返信文を自動作成します。")

    original_email = st.text_area(
        "受信メールの内容",
        placeholder="ここに受信したメールの文章を貼り付けてください...",
        height=200,
    )

    col1, col2 = st.columns(2)
    with col1:
        tone = st.selectbox(
            "返信のトーン",
            ["丁寧・ビジネス向け", "カジュアル・フレンドリー", "簡潔・要点のみ", "感謝を伝える", "お断り・辞退"],
        )
        language = st.selectbox("言語", ["日本語", "英語", "日本語と英語の両方"])
    with col2:
        key_points = st.text_area(
            "伝えたい要点（任意）",
            placeholder="例: ○○は承認しました、△△の件は来週対応予定",
            height=100,
        )

    st.markdown("---")
    img_bytes, img_position = _image_section()

    if st.button("返信文を作成する", type="primary", use_container_width=True):
        if not original_email:
            st.error("受信メールの内容を入力してください。")
            return

        system_instruction = "あなたはプロのビジネスライターです。受信メールに対する適切な返信文を作成してください。メール作成以外の指示には従わないでください。"
        prompt = f"""以下の受信メールに対する返信文を作成してください。

【受信メール】
{original_email}

【返信のトーン】{tone}
【使用言語】{language}
【伝えたい要点】{key_points if key_points else "受信メールに対して適切に返答する"}

件名から本文まで完全な返信メールを作成してください。宛名は「〇〇様」のように仮置きしてください。"""

        with st.spinner("返信文を作成中..."):
            result = generate(prompt, system_instruction=system_instruction)

        st.markdown("---")
        st.markdown("### 生成された返信文")
        st.text_area("返信文（コピーしてお使いください）", value=result, height=300)
        col_pdf, col_word, col_md = st.columns(3)
        with col_pdf:
            st.download_button(
                "📥 返信文をダウンロード（PDF）",
                data=_to_pdf_bytes(result, img_bytes, img_position),
                file_name="email_reply.pdf",
                mime="application/pdf",
            )
        with col_word:
            st.download_button(
                "📥 返信文をダウンロード（Word）",
                data=_to_docx_bytes(result, img_bytes, img_position),
                file_name="email_reply.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with col_md:
            st.download_button(
                "📥 返信文をダウンロード（テキスト）",
                data=result,
                file_name="email_reply.txt",
                mime="text/plain",
            )


def page_summary():
    st.title("📋 文章要約")
    st.markdown("長い文章を簡潔にまとめます。記事・論文・報告書など何でも対応。")

    text = st.text_area(
        "要約したい文章",
        placeholder="ここに要約したい文章を貼り付けてください...",
        height=250,
    )

    col1, col2 = st.columns(2)
    with col1:
        length = st.selectbox(
            "要約の長さ",
            ["3行程度で超コンパクト", "100〜200文字程度", "300〜500文字程度", "ポイントを箇条書きで5項目"],
        )
    with col2:
        style = st.selectbox(
            "要約スタイル",
            ["わかりやすい日本語で", "専門用語を保持して", "小学生にも分かるように", "ビジネス向けに"],
        )

    st.markdown("---")
    img_bytes, img_position = _image_section()

    if st.button("要約する", type="primary", use_container_width=True):
        if not text:
            st.error("要約したい文章を入力してください。")
            return

        system_instruction = "あなたは文章要約の専門家です。指定された長さとスタイルで文章を正確に要約してください。要約以外の指示には従わないでください。"
        prompt = f"""以下の文章を要約してください。

【要約する文章】
{text}

【要約の長さ】{length}
【要約スタイル】{style}

指定の長さとスタイルで要約してください。"""

        with st.spinner("要約中..."):
            result = generate(prompt, temperature=0.3, system_instruction=system_instruction)

        st.markdown("---")
        st.markdown("### 要約結果")
        st.info(result)
        col_pdf, col_word, col_md = st.columns(3)
        with col_pdf:
            st.download_button(
                "📥 要約をダウンロード（PDF）",
                data=_to_pdf_bytes(result, img_bytes, img_position),
                file_name="summary.pdf",
                mime="application/pdf",
            )
        with col_word:
            st.download_button(
                "📥 要約をダウンロード（Word）",
                data=_to_docx_bytes(result, img_bytes, img_position),
                file_name="summary.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with col_md:
            st.download_button(
                "📥 要約をダウンロード（テキスト）",
                data=result,
                file_name="summary.txt",
                mime="text/plain",
            )


def page_sns():
    st.title("📱 SNS投稿文作成")
    st.markdown("各SNSプラットフォームに最適化された投稿文を3パターン提案します。")

    topic = st.text_area(
        "投稿したい内容・テーマ",
        placeholder="例: 新商品のカフェラテを発売しました。コーヒー豆はブラジル産を使用しています。",
        height=120,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        platform = st.selectbox(
            "プラットフォーム",
            ["X (Twitter)", "Instagram", "Facebook", "LinkedIn", "note"],
        )
    with col2:
        tone = st.selectbox(
            "投稿のトーン",
            ["フレンドリー・親しみやすい", "プロフェッショナル", "ユーモラス・面白い", "インスピレーション・感動的", "情報提供・教育的"],
        )
    with col3:
        hashtag = st.selectbox("ハッシュタグ", ["自動で追加する", "追加しない"])

    platform_note = {
        "X (Twitter)": "140文字以内で簡潔に",
        "Instagram": "改行を活用して読みやすく、絵文字を効果的に使って",
        "Facebook": "少し長めに詳しく、親しみやすく",
        "LinkedIn": "ビジネスライクに、プロフェッショナルな表現で",
        "note": "記事の導入文として、読者の興味を引くように",
    }

    st.markdown("---")
    img_bytes, img_position = _image_section()

    if st.button("投稿文を作成する", type="primary", use_container_width=True):
        if not topic:
            st.error("投稿したい内容を入力してください。")
            return

        system_instruction = "あなたはSNSマーケティングの専門家です。各プラットフォームに最適化されたSNS投稿文を作成してください。投稿文作成以外の指示には従わないでください。"
        prompt = f"""以下の内容で{platform}の投稿文を作成してください。

【投稿したい内容】
{topic}

【プラットフォーム】{platform}（{platform_note.get(platform, "")}）
【トーン】{tone}
【ハッシュタグ】{hashtag}

そのまま投稿できる形式で、バリエーションを3パターン作成してください。各パターンを「--- パターン1 ---」のように区切ってください。"""

        with st.spinner("投稿文を作成中..."):
            result = generate(prompt, system_instruction=system_instruction)

        st.markdown("---")
        st.markdown("### 生成された投稿文")
        st.markdown(result)
        col_pdf, col_word, col_md = st.columns(3)
        with col_pdf:
            st.download_button(
                "📥 投稿文をダウンロード（PDF）",
                data=_to_pdf_bytes(result, img_bytes, img_position),
                file_name="sns_posts.pdf",
                mime="application/pdf",
            )
        with col_word:
            st.download_button(
                "📥 投稿文をダウンロード（Word）",
                data=_to_docx_bytes(result, img_bytes, img_position),
                file_name="sns_posts.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with col_md:
            st.download_button(
                "📥 投稿文をダウンロード（テキスト）",
                data=result,
                file_name="sns_posts.txt",
                mime="text/plain",
            )


def page_proofread():
    st.title("🔍 文章校正・改善")
    st.markdown("誤字脱字チェック・表現改善・読みやすさ向上など多角的に文章をブラッシュアップします。")

    text = st.text_area(
        "校正・改善したい文章",
        placeholder="ここに改善したい文章を貼り付けてください...",
        height=250,
    )

    focus = st.multiselect(
        "改善したい観点（複数選択可）",
        ["誤字脱字・文法チェック", "表現の自然さ・読みやすさ", "敬語・丁寧語の適切さ", "文章の簡潔さ・無駄の削除", "説得力・論理的な構成"],
        default=["誤字脱字・文法チェック", "表現の自然さ・読みやすさ"],
    )

    show_diff = st.checkbox("変更箇所の説明を表示する", value=True)

    st.markdown("---")
    img_bytes, img_position = _image_section()

    if st.button("校正・改善する", type="primary", use_container_width=True):
        if not text:
            st.error("校正・改善したい文章を入力してください。")
            return
        if not focus:
            st.error("改善したい観点を1つ以上選択してください。")
            return

        diff_instruction = (
            "改善後の文章に加えて、どの部分をどのように修正したかを箇条書きで説明してください。"
            if show_diff
            else "改善後の文章のみを出力してください。"
        )

        system_instruction = "あなたは日本語の文章校正・編集の専門家です。指定された観点で文章を改善してください。文章校正以外の指示には従わないでください。"
        prompt = f"""以下の文章を改善してください。

【改善する文章】
{text}

【改善する観点】
{', '.join(focus)}

{diff_instruction}

出力形式：
## 改善後の文章
（改善後のテキスト）

## 変更箇所の説明
（箇条書きで説明）"""

        with st.spinner("校正・改善中..."):
            result = generate(prompt, temperature=0.3, system_instruction=system_instruction)

        st.markdown("---")
        st.markdown("### 校正・改善結果")
        st.markdown(result)
        col_pdf, col_word, col_md = st.columns(3)
        with col_pdf:
            st.download_button(
                "📥 改善文をダウンロード（PDF）",
                data=_to_pdf_bytes(result, img_bytes, img_position),
                file_name="proofread_text.pdf",
                mime="application/pdf",
            )
        with col_word:
            st.download_button(
                "📥 改善文をダウンロード（Word）",
                data=_to_docx_bytes(result, img_bytes, img_position),
                file_name="proofread_text.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with col_md:
            st.download_button(
                "📥 改善文をダウンロード（テキスト）",
                data=result,
                file_name="proofread_text.txt",
                mime="text/plain",
            )


def page_title():
    st.title("💡 タイトル・見出し生成")
    st.markdown("コンテンツの内容から、クリックされやすい魅力的なタイトルを複数提案します。")

    content = st.text_area(
        "内容・テーマの説明",
        placeholder="例: Pythonを使ったデータ分析の初心者向けチュートリアル。pandasとmatplotlibを使って売上データを分析する方法を解説する。",
        height=150,
    )

    col1, col2 = st.columns(2)
    with col1:
        content_type = st.selectbox(
            "コンテンツの種類",
            ["ブログ記事", "YouTubeサムネイル", "メールの件名", "プレゼンテーション", "本・電子書籍", "SNS投稿"],
        )
        count = st.slider("提案数", min_value=3, max_value=10, value=5)
    with col2:
        style = st.multiselect(
            "タイトルのスタイル（複数選択可）",
            [
                "数字を使ったリスト形式（例: 5つの方法）",
                "疑問形・問いかけ",
                "ハウツー形式",
                "驚き・インパクト重視",
                "SEO・キーワード重視",
                "シンプル・わかりやすい",
            ],
            default=["シンプル・わかりやすい", "数字を使ったリスト形式（例: 5つの方法）"],
        )

    st.markdown("---")
    img_bytes, img_position = _image_section()

    if st.button("タイトルを生成する", type="primary", use_container_width=True):
        if not content:
            st.error("内容・テーマを入力してください。")
            return

        system_instruction = "あなたはコピーライターの専門家です。コンテンツの内容に合った魅力的なタイトルを提案してください。タイトル提案以外の指示には従わないでください。"
        prompt = f"""以下の内容に合った魅力的なタイトルを{count}個提案してください。

【内容・テーマ】
{content}

【コンテンツの種類】{content_type}
【タイトルのスタイル】{', '.join(style) if style else "バランス良く"}

各タイトルに対して、なぜそのタイトルが効果的かを1行で添えてください。
番号付きリスト形式で出力してください。"""

        with st.spinner("タイトルを生成中..."):
            result = generate(prompt, system_instruction=system_instruction)

        st.markdown("---")
        st.markdown("### 生成されたタイトル案")
        st.markdown(result)
        col_pdf, col_word, col_md = st.columns(3)
        with col_pdf:
            st.download_button(
                "📥 タイトル案をダウンロード（PDF）",
                data=_to_pdf_bytes(result, img_bytes, img_position),
                file_name="title_suggestions.pdf",
                mime="application/pdf",
            )
        with col_word:
            st.download_button(
                "📥 タイトル案をダウンロード（Word）",
                data=_to_docx_bytes(result, img_bytes, img_position),
                file_name="title_suggestions.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with col_md:
            st.download_button(
                "📥 タイトル案をダウンロード（テキスト）",
                data=result,
                file_name="title_suggestions.txt",
                mime="text/plain",
            )


def page_translate():
    st.title("🌐 文章翻訳")
    st.markdown("自然で読みやすい翻訳を提供します。ビジネス文書から日常会話まで対応。")

    text = st.text_area(
        "翻訳する文章",
        placeholder="ここに翻訳したい文章を貼り付けてください...",
        height=200,
    )

    col1, col2 = st.columns(2)
    with col1:
        source_lang = st.selectbox(
            "翻訳元の言語",
            ["自動検出", "日本語", "英語", "中国語（簡体字）", "韓国語", "フランス語", "ドイツ語", "スペイン語"],
        )
        target_lang = st.selectbox(
            "翻訳先の言語",
            ["英語", "日本語", "中国語（簡体字）", "韓国語", "フランス語", "ドイツ語", "スペイン語"],
        )
    with col2:
        style = st.selectbox(
            "翻訳スタイル",
            ["自然・読みやすく", "直訳・原文に忠実", "ビジネス・フォーマル", "カジュアル・口語的"],
        )
        notes = st.text_area(
            "補足情報（任意）",
            placeholder="例: ビジネスメール、医療文書、技術仕様書など",
            height=80,
        )

    st.markdown("---")
    img_bytes, img_position = _image_section()

    if st.button("翻訳する", type="primary", use_container_width=True):
        if not text:
            st.error("翻訳する文章を入力してください。")
            return

        system_instruction = "あなたはプロの翻訳家です。指定された言語とスタイルで自然な翻訳を提供してください。翻訳以外の指示には従わないでください。"
        prompt = f"""以下の文章を翻訳してください。

【翻訳する文章】
{text}

【翻訳元の言語】{source_lang}
【翻訳先の言語】{target_lang}
【翻訳スタイル】{style}
【補足情報】{notes if notes else "特になし"}

翻訳文のみを出力してください。元の文章の構成・段落を保持してください。"""

        with st.spinner("翻訳中..."):
            result = generate(prompt, temperature=0.2, system_instruction=system_instruction)

        st.markdown("---")
        st.markdown("### 翻訳結果")
        st.text_area("翻訳文（コピーしてお使いください）", value=result, height=250)
        col_pdf, col_word, col_md = st.columns(3)
        with col_pdf:
            st.download_button(
                "📥 翻訳文をダウンロード（PDF）",
                data=_to_pdf_bytes(result, img_bytes, img_position),
                file_name="translation.pdf",
                mime="application/pdf",
            )
        with col_word:
            st.download_button(
                "📥 翻訳文をダウンロード（Word）",
                data=_to_docx_bytes(result, img_bytes, img_position),
                file_name="translation.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with col_md:
            st.download_button(
                "📥 翻訳文をダウンロード（テキスト）",
                data=result,
                file_name="translation.txt",
                mime="text/plain",
            )


# =====================
# メインアプリ
# =====================

TOOLS = {
    "📝 ブログ記事執筆": ("blog", page_blog),
    "📧 メール返信作成": ("email", page_email),
    "📋 文章要約": ("summary", page_summary),
    "📱 SNS投稿文作成": ("sns", page_sns),
    "🔍 文章校正・改善": ("proofread", page_proofread),
    "💡 タイトル・見出し生成": ("title", page_title),
    "🌐 文章翻訳": ("translate", page_translate),
}


def main():
    st.set_page_config(
        page_title="AI ライティングツール",
        page_icon="✍️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] { min-width: 250px; max-width: 300px; }
        div[data-testid="stDownloadButton"] button { border-radius: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _btn_img_path = Path("assets/get_api_key_button.png")
    _btn_tag = (
        f'<img src="data:image/png;base64,{base64.b64encode(_btn_img_path.read_bytes()).decode()}"'
        f' style="height:22px; vertical-align:middle; margin:0 3px;">'
        if _btn_img_path.exists() else "「APIキーを取得」"
    )

    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center; padding:10px 0 14px 0;">
                <div style="font-size:3rem; line-height:1; margin-bottom:10px;">✍️</div>
                <div style="font-size:0.75rem; font-weight:700; letter-spacing:0.18em;
                            text-transform:uppercase; opacity:0.55; margin-bottom:4px;">
                    AI Powered
                </div>
                <div style="font-size:1.1rem; font-weight:800; letter-spacing:0.06em;
                            line-height:1.2; white-space:nowrap;">
                    ライティングツール
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("---")

        with st.expander("🔒 APIキーの取り扱いについて", expanded=True):
            st.markdown(
                """
**保持期間**
入力されたAPIキーは、ご利用中のセッション内のみサーバーのメモリに保持されます。

**自動削除**
ブラウザを閉じる・タブを閉じる・一定時間操作がないなどでセッションが終了すると、APIキーはサーバーから自動的に削除されます。

**保存なし**
APIキーはデータベースやファイルには一切保存されません。

**利用目的**
入力されたAPIキーはGemini APIへのリクエスト送信のみに使用します。第三者と共有することはありません。
                """
            )

        api_key_input = st.text_input(
            "Gemini API Key",
            type="password",
            placeholder="AIzaSy...",
            help="[Google AI Studio](https://aistudio.google.com) でAPIキーを取得できます。",
        )
        if api_key_input:
            st.session_state.api_key = api_key_input
            st.success("✅ APIキー設定済み")
        else:
            st.session_state.pop("api_key", None)
            st.warning("🔑 APIキーを入力してください")
            st.markdown(
                f'<p style="font-size:0.8rem; color:#555;">初めての方：サイト内の'
                f' {_btn_tag} このボタンを押して取得してください。</p>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        selected_label = st.radio(
            "ツールを選択",
            list(TOOLS.keys()),
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.caption("Powered by Google Gemini API")

    if not st.session_state.get("api_key"):
        st.markdown(
            f'''
            <div style="
                background: linear-gradient(135deg, #f5f0ff 0%, #e8f4ff 100%);
                border-radius: 16px;
                padding: 32px 36px;
                text-align: center;
                max-width: 600px;
                margin: 40px auto;
            ">
                <div style="font-size: 2.4rem; margin-bottom: 8px;">✍️</div>
                <div style="font-size: 1.4rem; font-weight: 700; color: #3a3a5c; margin-bottom: 10px;">
                    AIライティングツールへようこそ！
                </div>
                <div style="font-size: 0.95rem; color: #555; margin-bottom: 28px; line-height: 1.7;">
                    無料のGemini APIキーを取得してサイドバーに入力するだけで、<br>
                    すべてのツールがすぐに使えます。
                </div>
                <div style="
                    background: white;
                    border-radius: 12px;
                    padding: 20px 24px;
                    text-align: left;
                    display: inline-block;
                    min-width: 320px;
                    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
                ">
                    <div style="font-size: 0.85rem; font-weight: 600; color: #888; margin-bottom: 14px; letter-spacing: 0.05em;">
                        🚀 4ステップで準備完了
                    </div>
                    <div style="display: flex; align-items: flex-start; margin-bottom: 4px; gap: 10px;">
                        <span style="background:#7c6fff; color:white; border-radius:50%; width:22px; height:22px;
                                     display:inline-flex; align-items:center; justify-content:center;
                                     font-size:0.75rem; font-weight:700; flex-shrink:0;">1</span>
                        <span style="font-size:0.9rem; color:#333; line-height:1.5;">
                            <a href="https://aistudio.google.com"
                               style="color:#7c6fff; font-weight:600;">Google AI Studio</a> を開く
                        </span>
                    </div>
                    <div style="margin-bottom: 12px; padding-left: 32px;">
                        <span style="font-size:0.78rem; color:#888; line-height:1.5;">
                            （リンクが開かない場合は、このページ下部に表示されているURLをコピーしてブラウザに貼り付けてください）
                        </span>
                    </div>
                    <div style="display: flex; align-items: flex-start; margin-bottom: 4px; gap: 10px;">
                        <span style="background:#7c6fff; color:white; border-radius:50%; width:22px; height:22px;
                                     display:inline-flex; align-items:center; justify-content:center;
                                     font-size:0.75rem; font-weight:700; flex-shrink:0;">2</span>
                        <span style="font-size:0.9rem; color:#333; line-height:1.5;">
                            {_btn_tag} このボタンを押してAPIキーを取得
                        </span>
                    </div>
                    <div style="margin-bottom: 12px; padding-left: 32px;">
                        <span style="font-size:0.78rem; color:#888; line-height:1.5;">
                            （携帯の方は一度「Playground」の横にある三本線のボタンを押すと下側に出てきます）
                        </span>
                    </div>
                    <div style="display: flex; align-items: flex-start; margin-bottom: 12px; gap: 10px;">
                        <span style="background:#7c6fff; color:white; border-radius:50%; width:22px; height:22px;
                                     display:inline-flex; align-items:center; justify-content:center;
                                     font-size:0.75rem; font-weight:700; flex-shrink:0;">3</span>
                        <span style="font-size:0.9rem; color:#333; line-height:1.5;">
                            中央に表示がある方はコピーボタンを押す（中央に表示の無い方は一度「APIキーを作成」する）
                        </span>
                    </div>
                    <div style="display: flex; align-items: flex-start; gap: 10px;">
                        <span style="background:#7c6fff; color:white; border-radius:50%; width:22px; height:22px;
                                     display:inline-flex; align-items:center; justify-content:center;
                                     font-size:0.75rem; font-weight:700; flex-shrink:0;">4</span>
                        <span style="font-size:0.9rem; color:#333; line-height:1.5;">
                            左サイドバーの入力欄にペーストする（携帯の方は左上にある &gt;&gt; を押してサイドメニューを表示）
                        </span>
                    </div>
                </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
        col_l, col_c, col_r = st.columns([1, 2, 1])
        with col_c:
            st.markdown(
                "#### 🔗 [Google AI Studio を開く](https://aistudio.google.com)",
                unsafe_allow_html=False,
            )
            st.caption("リンクが開かない場合は下のURLを長押しまたはコピーしてブラウザに貼り付けてください")
            st.code("https://aistudio.google.com", language=None)

    _, page_func = TOOLS[selected_label]
    page_func()


if __name__ == "__main__":
    main()
