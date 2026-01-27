async def _html_generation_agent(self, state: WorkflowState) -> WorkflowState:
    """Generate structured HTML using LLM - preserve image tags, structure later"""
    print("🎨 HTML Generation Agent...")
    
    # Extract data
    improved_content = state['improved_document'].get('improved_content', '')
    images = state['parsed_content'].get('images', [])
    pdf_path = state['pdf_path']
    workflow_mode = state['workflow_mode']
    
    print(f"DEBUG: Found {len(images)} images")
    print(f"DEBUG: Content length: {len(improved_content)}")
    
    # Step 1: Ask LLM to structure content (keeps [IMAGE_X_Y_ANALYSIS] tags intact)
    structured_content = await self._structure_content_with_llm(improved_content)
    
    # Step 2: Replace [IMAGE_X_Y_ANALYSIS] tags with actual base64 images
    final_content = self._replace_image_tags_with_images(structured_content, images)
    
    # Step 3: Generate final HTML
    html_result = self._generate_final_html(final_content, pdf_path, workflow_mode)
    
    state['generated_html'] = html_result
    state['current_step'] = 'html_generation_complete'
    return state

async def _structure_content_with_llm(self, content: str) -> str:
    """Use LLM to add HTML structure WITHOUT changing content or image tags"""
    
    structuring_prompt = f"""You are an HTML formatting expert. Your task is to convert plain text content into well-structured HTML.

CRITICAL RULES:
1. DO NOT change, rephrase, or alter ANY of the original text content
2. DO NOT add new content or remove existing content
3. ONLY add HTML structure tags (h1, h2, h3, p, ul, li, etc.) to organize the existing content
4. PRESERVE ALL [IMAGE_X_Y_ANALYSIS]...[END_IMAGE_X_Y_ANALYSIS] blocks EXACTLY as they appear
5. Do NOT modify, remove, or wrap image analysis blocks in any way
6. Keep the image blocks on their own lines with no additional tags around them

HTML STRUCTURE TO ADD:
- Use <h1> for the main document title (if clearly identifiable)
- Use <h2> for major section headings
- Use <h3> for subsection headings
- Use <h4> for minor headings
- Use <p> for paragraphs (wrap text in paragraph tags)
- Use <ul> and <li> for bullet points or unordered lists
- Use <ol> and <li> for numbered lists
- Use <strong> for important terms or bold text
- Use <em> for emphasis or italic text
- Keep proper spacing between sections

WHAT TO IDENTIFY AS HEADINGS:
- Lines in ALL CAPS
- Lines ending with colon (:)
- Short lines (< 60 characters) that introduce new topics or sections
- Lines that clearly indicate a new section or topic
- Lines that are standalone and not part of a paragraph

WHAT NOT TO WRAP:
- [IMAGE_X_Y_ANALYSIS] blocks - leave these EXACTLY as they are
- Do NOT wrap image blocks in <p>, <div>, or any other tags

ORIGINAL CONTENT:
{content}

OUTPUT FORMAT:
Return ONLY the HTML-structured content. Do NOT include:
- <html>, <head>, <body> tags
- CSS styles
- JavaScript
- Meta tags
- Explanations, comments, or notes
- Markdown code blocks (no ```html```)

Start your response with the structured HTML immediately."""

    try:
        response = await self.llm.ainvoke([HumanMessage(content=structuring_prompt)])
        structured_html = response.content.strip()
        
        # Clean up any code block markers
        structured_html = structured_html.replace('```html', '').replace('```', '').strip()
        
        print(f"DEBUG: LLM structured content length: {len(structured_html)}")
        print(f"DEBUG: Image tags in structured content: {structured_html.count('[IMAGE_')}")
        
        return structured_html
        
    except Exception as e:
        print(f"⚠️ LLM structuring failed: {e}")
        # Fallback: simple paragraph wrapping, preserve image tags
        lines = content.split('\n')
        structured = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if '[IMAGE_' in line or '[END_IMAGE_' in line:
                structured.append(line)  # Keep image tags as-is
            elif line:
                structured.append(f'<p>{line}</p>')
        return '\n'.join(structured)

def _replace_image_tags_with_images(self, content: str, images: List[Dict]) -> str:
    """Replace [IMAGE_X_Y_ANALYSIS]...[END_IMAGE_X_Y_ANALYSIS] with base64 images"""
    import re
    
    print(f"DEBUG: Starting image replacement, {len(images)} images available")
    
    # Create lookup by (page, index)
    image_lookup = {(img['page'], img['image_index']): img for img in images}
    
    print(f"DEBUG: Image lookup created with {len(image_lookup)} entries")
    for key in image_lookup.keys():
        print(f"DEBUG: Registered image at page={key[0]}, index={key[1]}")
    
    # Pattern: [IMAGE_page_index_ANALYSIS]...[END_IMAGE_page_index_ANALYSIS]
    pattern = r'\[IMAGE_(\d+)_(\d+)_ANALYSIS\](.*?)\[END_IMAGE_\1_\2_ANALYSIS\]'
    
    def create_image_replacement(match):
        page_num = int(match.group(1))
        img_index = int(match.group(2))
        
        print(f"DEBUG: Processing image tag page={page_num}, index={img_index}")
        
        # Lookup image data
        img_data = image_lookup.get((page_num, img_index))
        
        if not img_data:
            print(f"⚠️ DEBUG: No image found for page={page_num}, index={img_index}")
            return "[IMAGE DATA MISSING]"
        
        if 'base64' not in img_data:
            print(f"⚠️ DEBUG: No base64 data for page={page_num}, index={img_index}")
            return "[IMAGE BASE64 MISSING]"
        
        print(f"✅ DEBUG: Found image for page={page_num}, index={img_index}")
        
        # Create base64 embedded image with caption
        img_src = f"data:image/png;base64,{img_data['base64']}"
        img_alt = img_data['image_description'].replace('"', '&quot;').replace("'", "&#39;")
        img_desc = img_data['image_description']
        
        img_html = f'''
<div class="image-wrapper">
    <img src="{img_src}" alt="{img_alt}" class="document-image">
    <p class="image-caption">{img_desc}</p>
</div>
'''
        
        return img_html
    
    # Replace all image tags
    content_with_images = re.sub(pattern, create_image_replacement, content, flags=re.DOTALL)
    
    # Check for remaining unprocessed tags
    remaining_tags = re.findall(r'\[IMAGE_\d+_\d+_ANALYSIS\]', content_with_images)
    if remaining_tags:
        print(f"⚠️ DEBUG: {len(remaining_tags)} image tags NOT replaced: {remaining_tags[:5]}")
    else:
        print(f"✅ DEBUG: All image tags successfully replaced")
    
    return content_with_images

def _generate_final_html(self, content: str, pdf_path: str, workflow_mode: str) -> Dict[str, str]:
    """Generate complete HTML document with structured content and images"""
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
            max-width: 1100px; 
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
            padding: 20px;
            background: #f7fafc;
            border-radius: 15px;
            text-align: center;
        }}
        
        .document-image {{ 
            max-width: 100%; 
            height: auto; 
            border-radius: 12px; 
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
            padding: 0 20px;
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
            .image-wrapper {{ padding: 15px; }}
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
    
    print(f"DEBUG: Final HTML generated, length={len(html_content)}, filename={filename}")
    return {
        'content': html_content,
        'filename': filename
    }
