def _structure_content_as_html(self, content: str) -> str:
    """Convert plain text content to structured HTML with proper formatting"""
    import re
    
    # Split into paragraphs
    paragraphs = content.split('\n\n')
    structured_html = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        # ✅ Detect headings (lines ending with : or ALL CAPS)
        if para.isupper() and len(para) < 100:
            structured_html += f'<h2>{para}</h2>\n'
        elif para.endswith(':') and len(para) < 100:
            structured_html += f'<h3>{para}</h3>\n'
        # ✅ Detect lists (lines starting with -, *, •, numbers)
        elif re.match(r'^[\-\*•]\s', para) or re.match(r'^\d+\.\s', para):
            items = para.split('\n')
            structured_html += '<ul>\n'
            for item in items:
                item = re.sub(r'^[\-\*•\d+\.]\s*', '', item).strip()
                if item:
                    structured_html += f'  <li>{item}</li>\n'
            structured_html += '</ul>\n'
        # ✅ Regular paragraphs
        else:
            # Preserve line breaks within paragraph
            para_html = para.replace('\n', '<br>\n')
            structured_html += f'<p>{para_html}</p>\n'
    
    return structured_html




def _generate_clean_html(self, content: str, pdf_path: str, workflow_mode: str) -> Dict[str, str]:
    """Generate structured HTML document"""
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    clean_name = Path(pdf_path).stem.replace('.pdf', '').replace('.txt', '') or 'document'
    filename = f"KAT_{clean_name}_{timestamp}.html"
    mode_title = "Content Improvement" if workflow_mode == 'content_improvement' else "Full Automation"
    
    # ✅ STRUCTURE THE CONTENT FIRST
    structured_content = self._structure_content_as_html(content)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{mode_title} - {clean_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            line-height: 1.8; color: #2d3748; 
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); 
            padding: 40px 20px; 
        }}
        .container {{ 
            max-width: 1000px; margin: 0 auto; 
            background: white; border-radius: 20px; 
            box-shadow: 0 25px 80px rgba(0,0,0,0.15); overflow: hidden; 
        }}
        .header {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 50px 40px; text-align: center; 
        }}
        .header h1 {{ font-size: 3em; margin-bottom: 15px; font-weight: 700; letter-spacing: -1px; }}
        .header p {{ font-size: 1.2em; opacity: 0.95; }}
        .content {{ padding: 60px 50px; }}
        .document-content {{ font-size: 1.1em; line-height: 1.9; color: #4a5568; }}
        
        /* ✅ STRUCTURED TYPOGRAPHY */
        .document-content h1 {{ 
            font-size: 2.5em; color: #1a202c; 
            margin: 50px 0 25px 0; font-weight: 700;
            border-bottom: 4px solid #667eea; padding-bottom: 15px;
        }}
        .document-content h2 {{ 
            font-size: 2em; color: #2d3748; 
            margin: 40px 0 20px 0; font-weight: 600;
            border-left: 5px solid #667eea; padding-left: 20px;
        }}
        .document-content h3 {{ 
            font-size: 1.5em; color: #4a5568; 
            margin: 30px 0 15px 0; font-weight: 600;
        }}
        .document-content p {{ 
            margin-bottom: 20px; 
            text-align: justify;
            line-height: 1.9;
        }}
        .document-content ul, .document-content ol {{ 
            margin: 20px 0 20px 40px; 
            line-height: 2;
        }}
        .document-content li {{ 
            margin-bottom: 12px; 
            padding-left: 10px;
        }}
        .document-content ul li {{
            list-style-type: disc;
        }}
        .document-content img {{ 
            max-width: 100%; height: auto; 
            border-radius: 15px; 
            margin: 40px auto; 
            display: block; 
            box-shadow: 0 15px 50px rgba(0,0,0,0.2);
            border: 1px solid #e2e8f0;
        }}
        .document-content strong {{ 
            color: #2d3748; font-weight: 600; 
        }}
        .document-content em {{ 
            color: #667eea; font-style: italic; 
        }}
        .document-content blockquote {{
            border-left: 5px solid #667eea;
            margin: 30px 0;
            padding: 20px 30px;
            background: #f7fafc;
            font-style: italic;
        }}
        
        .footer {{ 
            background: #2d3748; color: white; 
            text-align: center; padding: 35px; font-size: 0.95em; 
        }}
        
        @media (max-width: 768px) {{
            .content {{ padding: 40px 25px; }}
            .header h1 {{ font-size: 2em; }}
            .document-content h1 {{ font-size: 1.8em; }}
            .document-content h2 {{ font-size: 1.5em; }}
        }}
        @media print {{ 
            body {{ background: white !important; padding: 0 !important; }} 
            .container {{ box-shadow: none !important; border-radius: 0 !important; }} 
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 Improved Document</h1>
            <p>{mode_title} | {clean_name}</p>
        </div>
        <div class="content">
            <div class="document-content">
                {structured_content}
            </div>
        </div>
        <div class="footer">
            <p>Generated by KAT AI System</p>
            <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>"""
    
    return {'content': html_content, 'filename': filename}
