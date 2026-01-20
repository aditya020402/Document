async def _html_generation_agent(self, state: WorkflowState) -> WorkflowState:
    """Generate clean HTML from improved content with image replacement only"""
    print("🎨 HTML Generation Agent...")
    
    # Extract ONLY what's needed
    improved_content = state['improved_document'].get('improved_content', '')
    images = state['parsed_content'].get('images', [])
    pdf_path = state['pdf_path']
    
    # Replace image tags with actual images
    content_with_images = self._replace_image_tags_with_images(improved_content, images)
    
    # Generate clean HTML
    html_result = self._generate_clean_html(content_with_images, pdf_path, state['workflow_mode'])
    
    state['generated_html'] = html_result
    state['current_step'] = 'html_generation_complete'
    return state

def _replace_image_tags_with_images(self, content: str, images: List[Dict]) -> str:
    """Replace [IMAGE_{index}_ANALYSIS]...[END_IMAGE_{index}_ANALYSIS] with <img> tags"""
    import re
    
    # Create image lookup by index
    image_lookup = {img['image_index']: img for img in images}
    
    # Pattern for [IMAGE_X_ANALYSIS]...[END_IMAGE_X_ANALYSIS]
    pattern = r'\[IMAGE_(\d+)_ANALYSIS\].*?\[END_IMAGE_\1_ANALYSIS\]'
    
    def create_image_replacement(match):
        img_index = int(match.group(1))
        img_data = image_lookup.get(img_index)
        
        if not img_data:
            return ""  # Remove tag if no image data
        
        # ✅ Use file_path for src, description for alt
        img_src = img_data['file_path'].replace('\\', '/')
        img_alt = img_data['image_description'].replace('"', '&quot;')
        
        return f'<img src="{img_src}" alt="{img_alt}" style="max-width:100%; height:auto; border-radius:8px; margin:20px 0; box-shadow:0 5px 15px rgba(0,0,0,0.1);">'
    
    # Replace all image blocks with <img> tags
    content_with_images = re.sub(pattern, create_image_replacement, content, flags=re.DOTALL)
    
    return content_with_images

def _generate_clean_html(self, content: str, pdf_path: str, workflow_mode: str) -> Dict[str, str]:
    """Generate minimal HTML with just the improved content + images"""
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    clean_name = Path(pdf_path).stem.replace('.pdf', '').replace('.txt', '') or 'document'
    filename = f"KAT_{clean_name}_{timestamp}.html"
    
    mode_title = "Content Improvement" if workflow_mode == 'content_improvement' else "Full Automation"
    
    # ✅ CLEAN HTML - NO METRICS, JUST CONTENT
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{mode_title} - {clean_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.7;
            color: #333;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 40px 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 25px 80px rgba(0,0,0,0.15);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.8em;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        .header p {{
            font-size: 1.2em;
            opacity: 0.95;
        }}
        .content {{
            padding: 50px;
            max-width: 900px;
            margin: 0 auto;
        }}
        .document-content {{
            font-size: 1.1em;
            line-height: 1.8;
        }}
        .document-content img {{
            max-width: 100%;
            height: auto;
            border-radius: 12px;
            margin: 30px 0;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            display: block;
        }}
        .document-content h1, .document-content h2 {{
            color: #4a5568;
            margin: 40px 0 20px 0;
            font-weight: 600;
        }}
        .document-content p {{
            margin-bottom: 20px;
        }}
        .footer {{
            background: #2d3748;
            color: white;
            text-align: center;
            padding: 30px;
            font-size: 0.95em;
        }}
        @media (max-width: 768px) {{
            .content {{
                padding: 30px 20px;
            }}
            .header h1 {{
                font-size: 2em;
            }}
        }}
        @media print {{
            body {{ background: white !important; padding: 0 !important; }}
            .container {{ box-shadow: none !important; border-radius: 0 !important; }}
            .header {{ -webkit-print-color-adjust: exact; color-adjust: exact; }}
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
                {content}
            </div>
        </div>
        
        <div class="footer">
            <p>Generated by KAT AI System</p>
            <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>"""
    
    return {
        'content': html_content,
        'filename': filename
    }
