class HTMLDocumentGenerator:
    UBS_RED = "#E60000"
    UBS_DARK_RED = "#B30000"
    UBS_GRAY = "#666666"
    UBS_LIGHT_GRAY = "#F5F5F5"

    def _get_css_styles(self) -> str:
        return f"""
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, sans-serif;
                line-height: 1.7;
                background-color: #f9f9f9;
                padding: 20px;
                color: #333333;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                box-shadow: 0 0 15px rgba(0,0,0,0.08);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, {self.UBS_RED} 0%, {self.UBS_DARK_RED} 100%);
                color: white;
                padding: 32px 40px;
                text-align: left;
            }}
            .header-logo {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 64px;
                height: 64px;
                background: white;
                border-radius: 10px;
                margin-bottom: 12px;
            }}
            .header-logo-text {{
                color: {self.UBS_RED};
                font-size: 28px;
                font-weight: 700;
            }}
            .header h1 {{
                margin: 4px 0 0 0;
                font-size: 26px;
                font-weight: 600;
            }}
            .header .subtitle {{
                margin-top: 4px;
                font-size: 14px;
                opacity: 0.9;
            }}
            .content {{
                padding: 32px 40px 40px 40px;
            }}
            .doc-title {{
                font-size: 22px;
                color: {self.UBS_RED};
                border-bottom: 2px solid {self.UBS_RED};
                padding-bottom: 8px;
                margin-bottom: 20px;
            }}
            .meta {{
                font-size: 12px;
                color: {self.UBS_GRAY};
                margin-bottom: 24px;
            }}
            .paragraph {{
                margin: 12px 0;
                text-align: justify;
            }}
            .important {{
                background-color: #FFE6E6;
                border-left: 4px solid #E60000;
                padding: 14px 16px;
                border-radius: 4px;
                margin: 16px 0;
            }}
            .important::before {{
                content: "IMPORTANT: ";
                font-weight: 600;
                color: #E60000;
            }}
            .warning {{
                background-color: #FFF3E0;
                border-left: 4px solid #FFA500;
                padding: 14px 16px;
                border-radius: 4px;
                margin: 16px 0;
            }}
            .warning::before {{
                content: "WARNING: ";
                font-weight: 600;
                color: #FFA500;
            }}
            .tip {{
                background-color: #FFFACD;
                border-left: 4px solid #FFD700;
                padding: 14px 16px;
                border-radius: 4px;
                margin: 16px 0;
            }}
            .tip::before {{
                content: "TIP: ";
                font-weight: 600;
                color: #DAA520;
            }}
            .success {{
                background-color: #E8F5E9;
                border-left: 4px solid #28A745;
                padding: 14px 16px;
                border-radius: 4px;
                margin: 16px 0;
            }}
            .success::before {{
                content: "BEST PRACTICE: ";
                font-weight: 600;
                color: #28A745;
            }}
            .image-block {{
                margin: 24px 0;
                text-align: center;
                background: #ffffff;
                padding: 16px;
                border-radius: 6px;
                border: 1px solid #eeeeee;
            }}
            .image-block img {{
                max-width: 100%;
                height: auto;
                border-radius: 4px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            }}
            .image-caption {{
                margin-top: 8px;
                font-size: 12px;
                color: {self.UBS_GRAY};
                font-style: italic;
            }}
            .footer {{
                background: {self.UBS_LIGHT_GRAY};
                border-top: 3px solid {self.UBS_RED};
                padding: 20px;
                text-align: center;
                color: {self.UBS_GRAY};
                font-size: 11px;
            }}
            .footer-team {{
                color: {self.UBS_RED};
                font-weight: 600;
            }}
        </style>
        """

    def _encode_image(self, path: str) -> str:
        try:
            import base64
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return ""

    def _classify_block(self, text: str) -> str:
        t = text.strip()
        lower = t.lower()
        if any(k in lower for k in ["critical", "must", "mandatory", "important:"]):
            return f'<div class="important">{self._esc(t)}</div>'
        if any(k in lower for k in ["warning:", "caution", "risk", "avoid"]):
            return f'<div class="warning">{self._esc(t)}</div>'
        if any(k in lower for k in ["tip:", "hint", "suggestion", "recommend"]):
            return f'<div class="tip">{self._esc(t)}</div>'
        if any(k in lower for k in ["best practice", "recommended", "should be"]):
            return f'<div class="success">{self._esc(t)}</div>'
        return f'<p class="paragraph">{self._esc(t)}</p>'

    def _esc(self, text: str) -> str:
        return (str(text)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))

    def generate_html(self, analysis_results: Dict[str, Any], output_path: str | None = None) -> str:
        from datetime import datetime
        from pathlib import Path

        doc_name = analysis_results.get("document_name", "Document")
        workflow_mode = analysis_results.get("workflow_mode", "unknown")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 1) pick only improved content
        improved_content = None
        if isinstance(analysis_results.get("improved_document"), dict):
            improved_content = analysis_results["improved_document"].get("improved_content")
        if not improved_content and isinstance(analysis_results.get("cleaned_content"), dict):
            improved_content = analysis_results["cleaned_content"].get("cleaned_text", "")

        text_blocks: list[str] = []
        if isinstance(improved_content, str):
            # split into logical blocks (paragraphs)
            for block in improved_content.split("\n\n"):
                if block.strip():
                    text_blocks.append(block.strip())
        else:
            text_blocks.append(str(improved_content or ""))

        # 2) collect parsed images (paths only)
        images = []
        parsed = analysis_results.get("parsed_content") or {}
        if isinstance(parsed, dict) and isinstance(parsed.get("images"), list):
            for item in parsed["images"]:
                if isinstance(item, dict) and "path" in item:
                    images.append(item)

        # 3) build HTML
        parts: list[str] = []
        parts.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
        parts.append(f"<title>{self._esc(doc_name)} - KAT</title>")
        parts.append(self._get_css_styles())
        parts.append("</head><body>")
        parts.append('<div class="container">')

        # header
        parts.append("""
        <div class="header">
          <div class="header-logo">
            <div class="header-logo-text">UBS</div>
          </div>
          <h1>Knowledge Analysis Tool (KAT)</h1>
          <div class="subtitle">Final improved document</div>
        </div>
        """)

        # content
        parts.append('<div class="content">')
        parts.append(f'<div class="doc-title">{self._esc(doc_name)}</div>')
        parts.append(f'<div class="meta">Mode: {self._esc(workflow_mode)} · Generated: {self._esc(ts)}</div>')

        # improved content only
        for block in text_blocks:
            parts.append(self._classify_block(block))

        # images
        if images:
            parts.append("<h2 style='margin-top:28px;color:#666666;'>Images</h2>")
            for idx, img in enumerate(images, start=1):
                path = img.get("path", "")
                if not path or not Path(path).exists():
                    continue
                b64 = self._encode_image(path)
                if not b64:
                    continue
                page = img.get("page", "N/A")
                parts.append(
                    "<div class='image-block'>"
                    f"<img src='data:image/png;base64,{b64}' alt='Image {idx}'>"
                    f"<div class='image-caption'>Figure {idx} · Page {self._esc(page)}</div>"
                    "</div>"
                )

        parts.append("</div>")  # content

        # footer
        parts.append(f"""
        <div class="footer">
          <div class="footer-team">UBS · AI Engineering & Automation Excellence Team</div>
        </div>
        """)

        parts.append("</div></body></html>")
        html = "".join(parts)

        if output_path:
            Path(output_path).write_text(html, encoding="utf-8")
        return html
