async def _html_generation_agent(self, state: WorkflowState) -> WorkflowState:
    """Generate structured HTML using LLM to format content"""
    print("🎨 HTML Generation Agent...")
    
    # Extract data
    improved_content = state['improved_document'].get('improved_content', '')
    images = state['parsed_content'].get('images', [])
    pdf_path = state['pdf_path']
    workflow_mode = state['workflow_mode']
    
    print(f"DEBUG: Found {len(images)} images")
    print(f"DEBUG: Content length: {len(improved_content)}")
    
    # Step 1: Replace image tags with placeholders
    content_with_placeholders, image_map = self._replace_images_with_placeholders(improved_content, images)
    
    # Step 2: Ask LLM to structure the content
    structured_content = await self._structure_content_with_llm(content_with_placeholders)
    
    # Step 3: Replace placeholders with actual base64 images
    final_content = self._restore_images_from_placeholders(structured_content, image_map)
    
    # Step 4: Generate final HTML
    html_result = self._generate_final_html(final_content, pdf_path, workflow_mode)
    
    state['generated_html'] = html_result
    state['current_step'] = 'html_generation_complete'
    return state

def _replace_images_with_placeholders(self, content: str, images: List[Dict]) -> tuple:
    """Replace [IMAGE_X_Y_ANALYSIS]...[END_IMAGE_X_Y_ANALYSIS] with simple placeholders"""
    import re
    
    image_map = {}  # Store placeholder → image data mapping
    image_lookup = {(img['page'], img['image_index']): img for img in images}
    
    pattern = r'\[IMAGE_(\d+)_(\d+)_ANALYSIS\](.*?)\[END_IMAGE_\1_\2_ANALYSIS\]'
    
    def create_placeholder(match):
        page_num = int(match.group(1))
        img_index = int(match.group(2))
        
        img_data = image_lookup.get((page_num, img_index))
        if not img_data:
            return ""
        
        # Create simple placeholder
        placeholder = f"{{{{IMAGE_PLACEHOLDER_{page_num}_{img_index}}}}}"
        image_map[placeholder] = img_data
        
        return placeholder
    
    content_with_placeholders = re.sub(pattern, create_placeholder, content, flags=re.DOTALL)
    return content_with_placeholders, image_map

async def _structure_content_with_llm(self, content: str) -> str:
    """Use LLM to add HTML structure WITHOUT changing content"""
    
    structuring_prompt = f"""You are an HTML formatting expert. Your task is to convert plain text content into well-structured HTML.

CRITICAL RULES:
1. DO NOT change, rephrase, or alter ANY of the original text content
2. DO NOT add new content or remove existing content
3. ONLY add HTML structure tags to organize the existing content
4. Preserve ALL {{{{IMAGE_PLACEHOLDER_X_Y}}}} markers EXACTLY as they appear
5. Do NOT wrap image placeholders in any additional tags

HTML STRUCTURE TO ADD:
- Use <h1> for the main document title (if present)
- Use <h2> for major section headings
- Use <h3> for subsection headings
- Use <p> for paragraphs
- Use <ul> and <li> for bullet points or lists
- Use <ol> and <li> for numbered lists
- Use <strong> for important terms
- Use <em> for emphasis where appropriate
- Use <br> for line breaks within paragraphs if needed

WHAT TO IDENTIFY AS HEADINGS:
- Lines in ALL CAPS
- Lines ending with colon (:)
- Short lines (< 60 chars) that introduce new topics
- Lines with obvious heading patterns

ORIGINAL CONTENT:
{content}

OUTPUT FORMAT:
Return ONLY the HTML-structured content. Do NOT include:
- <html>, <head>, <body> tags
- CSS styles
- JavaScript
- Meta tags
- Explanations or comments

Start your response with the structured HTML immediately."""

    try:
        response = await self.llm.ainvoke([HumanMessage(content=structuring_prompt)])
        structured_html = response.content.strip()
        
        # Clean up any unwanted wrapper tags
        structured_html = structured_html.replace('```html', '').replace('```', '').strip()
        
        print(f"DEBUG: LLM structured content length: {len(structured_html)}")
        return structured_html
        
    except Exception as e:
        print(f"⚠️ LLM structuring failed: {e}")
        # Fallback: wrap in paragraphs
        paragraphs = content.split('\n\n')
        return '\n'.join([f'<p>{p.strip()}</p>' for p in paragraphs if p.strip()])

def _restore_images_from_placeholders(self, content: str, image_map: Dict) -> str:
    """Replace {{IMAGE_PLACEHOLDER_X_Y}} with actual base64 images"""
    
    for placeholder, img_data in image_map.items():
        if 'base64' not in img_data:
            content = content.replace(placeholder, "[IMAGE MISSING]")
            continue
        
        # Create base64 image tag
        img_src = f"data:image/png;base64,{img_data['base64']}"
        img_alt = img_data['image_description'].replace('"', '&quot;').replace("'", "&#39;")
        
        img_tag = f'''<div class="image-wrapper">
    <img src="{img_src}" alt="{img_alt}" class="document-image">
    <p class="image-caption">{img_data['image_description']}</p>
</div>'''
        
        content = content.replace(placeholder, img_tag)
    
    print(f"DEBUG: Restored {len(image_map)} images")
    return content

def _generate_final_html(self, content: str, pdf_path: str, workflow_mode: str) -> Dict[str, str]:
    """Generate complete HTML document with structured content"""
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    clean_name = Path(pdf_path).stem.replace('.pdf', '').replace('.txt', '') or 'document'
    filename = f"KAT_{clean_name}_{timestamp}.html"
    mode_title = "Content Improvement" if workflow_mode == 'content_improvement' else "Full Automation"
    
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
            line-height: 1.8; 
            color: #2d3748; 
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); 
            padding: 40px 20px; 
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
            padding: 50px 40px; 
            text-align: center; 
        }}
        
        .header h1 {{ 
            font-size: 3em; 
            margin-bottom: 15px; 
            font-weight: 700; 
            letter-spacing: -1px; 
        }}
        
        .header p {{ 
            font-size: 1.2em; 
            opacity: 0.95; 
        }}
        
        .content {{ 
            padding: 60px 50px; 
        }}
        
        .document-content {{ 
            font-size: 1.1em; 
            line-height: 1.9; 
            color: #4a5568; 
        }}
        
        /* Typography */
        .document-content h1 {{ 
            font-size: 2.5em; 
            color: #1a202c; 
            margin: 50px 0 25px 0; 
            font-weight: 700;
            border-bottom: 4px solid #667eea; 
            padding-bottom: 15px;
        }}
        
        .document-content h2 {{ 
            font-size: 2em; 
            color: #2d3748; 
            margin: 40px 0 20px 0; 
            font-weight: 600;
            border-left: 5px solid #667eea; 
            padding-left: 20px;
        }}
        
        .document-content h3 {{ 
            font-size: 1.5em; 
            color: #4a5568; 
            margin: 30px 0 15px 0; 
            font-weight: 600;
        }}
        
        .document-content h4 {{ 
            font-size: 1.2em; 
            color: #718096; 
            margin: 25px 0 12px 0; 
            font-weight: 600;
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
        
        .document-content ol li {{
            list-style-type: decimal;
        }}
        
        .document-content strong {{ 
            color: #2d3748; 
            font-weight: 600; 
        }}
        
        .document-content em {{ 
            color: #667eea; 
            font-style: italic; 
        }}
        
        .document-content blockquote {{
            border-left: 5px solid #667eea;
            margin: 30px 0;
            padding: 20px 30px;
            background: #f7fafc;
            font-style: italic;
            color: #4a5568;
        }}
        
        /* Images */
        .image-wrapper {{
            margin: 40px 0;
            text-align: center;
        }}
        
        .document-image {{ 
            max-width: 100%; 
            height: auto; 
            border-radius: 15px; 
            margin: 0 auto 20px auto; 
            display: block; 
            box-shadow: 0 15px 50px rgba(0,0,0,0.2);
            border: 1px solid #e2e8f0;
        }}
        
        .image-caption {{
            font-size: 0.95em;
            color: #718096;
            font-style: italic;
            margin-top: 10px;
        }}
        
        .footer {{ 
            background: #2d3748; 
            color: white; 
            text-align: center; 
            padding: 35px; 
            font-size: 0.95em; 
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .content {{ padding: 40px 25px; }}
            .header h1 {{ font-size: 2em; }}
            .document-content h1 {{ font-size: 1.8em; }}
            .document-content h2 {{ font-size: 1.5em; }}
            .document-content {{ font-size: 1em; }}
        }}
        
        /* Print */
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
    
    print(f"DEBUG: Final HTML generated, length={len(html_content)}")
    return {
        'content': html_content,
        'filename': filename
    }
