async def _html_generation_agent(self, state: WorkflowState) -> WorkflowState:
    """Generate HTML report from improved document with inline images"""
    print("🎨 HTML Generation Agent...")
    
    # Extract data
    improved_content = state['improved_document'].get('improved_content', '')
    images = state['parsed_content'].get('images', [])  # ✅ Using 'images'
    analysis = state['automation_analysis']
    workflow_mode = state['workflow_mode']
    pdf_path = state['pdf_path']
    
    # Generate HTML
    html_result = await self._generate_final_html_report(
        improved_content, images, analysis, workflow_mode, pdf_path
    )
    
    # Store in state
    state['generated_html'] = html_result
    
    state['current_step'] = 'html_generation_complete'
    return state

async def _generate_final_html_report(self, content: str, images: List[Dict], 
                                    analysis: Dict, workflow_mode: str, pdf_path: str) -> Dict[str, str]:
    """Generate complete HTML report with inline images + disk cleanup"""
    
    from datetime import datetime
    
    # Filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    clean_name = Path(pdf_path).stem.replace('.pdf', '').replace('.txt', '') or 'document'
    filename = f"KAT_{clean_name}_{timestamp}.html"
    
    # Quality scores
    quality_scores = analysis.get('quality_scores', {})
    overall_quality = analysis.get('overall_quality', {})
    
    clarity = quality_scores.get('clarity_score', 0)
    completeness = quality_scores.get('completeness_score', 0)
    overall = overall_quality.get('overall_score', 0)
    
    mode_title = "Content Improvement" if workflow_mode == 'content_improvement' else "Full Automation"
    
    # ✅ Replace image tags with HTML images
    content_with_images = await self._replace_image_tags_inline(content, images)
    
    # Complete HTML with inline CSS
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KAT Document Report - {mode_title}</title>
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            color: #4facfe;
            font-size: 1.8em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #4facfe;
        }}
        .improved-content {{
            background: #f0f8ff;
            padding: 25px;
            border-radius: 10px;
            border-left: 5px solid #4facfe;
            line-height: 1.8;
            font-size: 1.05em;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin: 25px 0;
        }}
        .metric-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 3em;
            font-weight: bold;
            color: #4facfe;
            display: block;
            margin-bottom: 10px;
        }}
        .metric-label {{
            font-size: 1em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .inline-image-container {{
            background: #f8f9ff;
            padding: 25px;
            border-radius: 12px;
            margin: 30px 0;
            border-left: 5px solid #4facfe;
            box-shadow: 0 5px 20px rgba(0,0,0,0.08);
        }}
        .inline-image-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        }}
        .image-analysis h4 {{
            color: #4facfe;
            margin-bottom: 15px;
            font-size: 1.3em;
        }}
        .image-analysis p {{
            margin: 12px 0;
            line-height: 1.6;
        }}
        .image-analysis strong {{
            color: #333;
        }}
        .footer {{
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 25px;
            font-size: 0.95em;
        }}
        @media (max-width: 768px) {{
            .metrics {{
                grid-template-columns: 1fr;
            }}
        }}
        @media print {{
            body {{
                background: white !important;
                padding: 0 !important;
            }}
            .container {{
                box-shadow: none !important;
                border-radius: 0 !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 KAT Document Analysis Report</h1>
            <p><strong>Mode:</strong> {mode_title} | <strong>File:</strong> {clean_name}</p>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>✨ Improved Document Content</h2>
                <div class="improved-content">
                    {content_with_images}
                </div>
            </div>
            
            <div class="section">
                <h2>📊 Quality Analysis</h2>
                <div class="metrics">
                    <div class="metric-card">
                        <span class="metric-value">{clarity}</span>
                        <span class="metric-label">Clarity Score</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-value">{completeness}</span>
                        <span class="metric-label">Completeness</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-value">{overall}</span>
                        <span class="metric-label">Overall Quality</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>Generated by KAT AI System</p>
            <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""
    
    return {
        'content': html_content,
        'filename': filename
    }

async def _replace_image_tags_inline(self, content: str, images: List[Dict]) -> str:
    """Replace [IMAGE_X_ANALYSIS] tags with embedded images at exact positions"""
    import re
    
    # Create image lookup by index
    image_lookup = {img['image_index']: img for img in images}
    
    # Replace all image blocks
    for img_num in sorted(image_lookup.keys()):
        if img_num in image_lookup:
            img = image_lookup[img_num]
            
            # ✅ Use base64 for embedding (disk file as fallback)
            img_src = f"data:image/png;base64,{img['base64']}"
            
            replacement = f"""
<div class="inline-image-container">
    <img src="{img_src}" alt="Document Image {img_num}">
    <div class="image-analysis">
        <h4>🔍 Image {img_num} Analysis (Page {img['page']})</h4>
        <p><strong>Description:</strong> {img['image_description']}</p>
        <p><strong>Purpose:</strong> {img['purpose']}</p>
        <p><strong>Extracted Text:</strong> {img['extracted_text']}</p>
        <p><strong>Automation Relevance:</strong> {img['automation_relevance']}</p>
    </div>
</div>
"""
            
            pattern = rf'\[IMAGE_{img_num}_ANALYSIS\].*?\[END_IMAGE_{img_num}_ANALYSIS\]'
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    return content





# new function for replacing the tags 



async def _html_generation_agent(self, state: WorkflowState) -> WorkflowState:
    """Generate HTML report from improved document with inline images"""
    print("🎨 HTML Generation Agent...")
    
    # Extract data
    improved_content = state['improved_document'].get('improved_content', '')
    images = state['parsed_content'].get('images', [])  # ✅ Using 'images'
    analysis = state['automation_analysis']
    workflow_mode = state['workflow_mode']
    pdf_path = state['pdf_path']
    
    # Generate HTML
    html_result = await self._generate_final_html_report(
        improved_content, images, analysis, workflow_mode, pdf_path
    )
    
    # Store in state
    state['generated_html'] = html_result
    
    state['current_step'] = 'html_generation_complete'
    return state

async def _generate_final_html_report(self, content: str, images: List[Dict], 
                                    analysis: Dict, workflow_mode: str, pdf_path: str) -> Dict[str, str]:
    """Generate complete HTML report with inline images + disk cleanup"""
    
    from datetime import datetime
    
    # Filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    clean_name = Path(pdf_path).stem.replace('.pdf', '').replace('.txt', '') or 'document'
    filename = f"KAT_{clean_name}_{timestamp}.html"
    
    # Quality scores
    quality_scores = analysis.get('quality_scores', {})
    overall_quality = analysis.get('overall_quality', {})
    
    clarity = quality_scores.get('clarity_score', 0)
    completeness = quality_scores.get('completeness_score', 0)
    overall = overall_quality.get('overall_score', 0)
    
    mode_title = "Content Improvement" if workflow_mode == 'content_improvement' else "Full Automation"
    
    # ✅ Replace image tags with HTML images
    content_with_images = await self._replace_image_tags_inline(content, images)
    
    # Complete HTML with inline CSS
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KAT Document Report - {mode_title}</title>
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            color: #4facfe;
            font-size: 1.8em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #4facfe;
        }}
        .improved-content {{
            background: #f0f8ff;
            padding: 25px;
            border-radius: 10px;
            border-left: 5px solid #4facfe;
            line-height: 1.8;
            font-size: 1.05em;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin: 25px 0;
        }}
        .metric-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 3em;
            font-weight: bold;
            color: #4facfe;
            display: block;
            margin-bottom: 10px;
        }}
        .metric-label {{
            font-size: 1em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .inline-image-container {{
            background: #f8f9ff;
            padding: 25px;
            border-radius: 12px;
            margin: 30px 0;
            border-left: 5px solid #4facfe;
            box-shadow: 0 5px 20px rgba(0,0,0,0.08);
        }}
        .inline-image-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        }}
        .image-analysis h4 {{
            color: #4facfe;
            margin-bottom: 15px;
            font-size: 1.3em;
        }}
        .image-analysis p {{
            margin: 12px 0;
            line-height: 1.6;
        }}
        .image-analysis strong {{
            color: #333;
        }}
        .footer {{
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 25px;
            font-size: 0.95em;
        }}
        @media (max-width: 768px) {{
            .metrics {{
                grid-template-columns: 1fr;
            }}
        }}
        @media print {{
            body {{
                background: white !important;
                padding: 0 !important;
            }}
            .container {{
                box-shadow: none !important;
                border-radius: 0 !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 KAT Document Analysis Report</h1>
            <p><strong>Mode:</strong> {mode_title} | <strong>File:</strong> {clean_name}</p>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>✨ Improved Document Content</h2>
                <div class="improved-content">
                    {content_with_images}
                </div>
            </div>
            
            <div class="section">
                <h2>📊 Quality Analysis</h2>
                <div class="metrics">
                    <div class="metric-card">
                        <span class="metric-value">{clarity}</span>
                        <span class="metric-label">Clarity Score</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-value">{completeness}</span>
                        <span class="metric-label">Completeness</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-value">{overall}</span>
                        <span class="metric-label">Overall Quality</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>Generated by KAT AI System</p>
            <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""
    
    return {
        'content': html_content,
        'filename': filename
    }

async def _replace_image_tags_inline(self, content: str, images: List[Dict]) -> str:
    """Replace [IMAGE_X_ANALYSIS] tags with embedded images at exact positions"""
    import re
    
    # Create image lookup by index
    image_lookup = {img['image_index']: img for img in images}
    
    # Replace all image blocks
    for img_num in sorted(image_lookup.keys()):
        if img_num in image_lookup:
            img = image_lookup[img_num]
            
            # ✅ Use base64 for embedding (disk file as fallback)
            img_src = f"data:image/png;base64,{img['base64']}"
            
            replacement = f"""
<div class="inline-image-container">
    <img src="{img_src}" alt="Document Image {img_num}">
    <div class="image-analysis">
        <h4>🔍 Image {img_num} Analysis (Page {img['page']})</h4>
        <p><strong>Description:</strong> {img['image_description']}</p>
        <p><strong>Purpose:</strong> {img['purpose']}</p>
        <p><strong>Extracted Text:</strong> {img['extracted_text']}</p>
        <p><strong>Automation Relevance:</strong> {img['automation_relevance']}</p>
    </div>
</div>
"""
            
            pattern = rf'\[IMAGE_{img_num}_ANALYSIS\].*?\[END_IMAGE_{img_num}_ANALYSIS\]'
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    return content
