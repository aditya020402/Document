import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import re


class HTMLDocumentGenerator:
    """
    Generate professional, color-coded HTML documents showing only improved content with images.
    """
    
    # UBS Color Scheme
    UBS_RED = "#E60000"
    UBS_DARK_RED = "#B30000"
    UBS_GRAY = "#666666"
    UBS_LIGHT_GRAY = "#F5F5F5"
    
    # Semantic Colors
    COLOR_IMPORTANT = "#E60000"  # Red for important items
    COLOR_WARNING = "#FFA500"    # Orange for warnings
    COLOR_TIP = "#FFD700"        # Gold for tips
    COLOR_SUCCESS = "#28A745"    # Green for success/best practices
    COLOR_INFO = "#007BFF"       # Blue for information
    COLOR_NOTE = "#6C757D"       # Gray for notes
    
    def __init__(self):
        self.html_content = []
        
    def _get_css_styles(self) -> str:
        """Generate CSS styles for the HTML document"""
        return f"""
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.8;
                color: #333;
                background-color: #f9f9f9;
                padding: 20px;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
                border-radius: 10px;
                overflow: hidden;
            }}
            
            .header {{
                background: linear-gradient(135deg, {self.UBS_RED} 0%, {self.UBS_DARK_RED} 100%);
                color: white;
                padding: 40px;
                text-align: center;
            }}
            
            .header-logo {{
                width: 80px;
                height: 80px;
                background: white;
                border-radius: 10px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 20px;
            }}
            
            .header-logo-text {{
                color: {self.UBS_RED};
                font-size: 36px;
                font-weight: bold;
            }}
            
            .header h1 {{
                font-size: 2.5rem;
                margin: 10px 0;
            }}
            
            .header .subtitle {{
                font-size: 1.1rem;
                opacity: 0.9;
            }}
            
            .content {{
                padding: 50px;
            }}
            
            .document-title {{
                color: {self.UBS_RED};
                font-size: 2.2rem;
                margin-bottom: 10px;
                padding-bottom: 15px;
                border-bottom: 3px solid {self.UBS_RED};
            }}
            
            .metadata {{
                background: {self.UBS_LIGHT_GRAY};
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 40px;
                border-left: 5px solid {self.UBS_RED};
            }}
            
            .metadata-item {{
                display: inline-block;
                margin-right: 30px;
                margin-bottom: 10px;
            }}
            
            .metadata-label {{
                font-weight: bold;
                color: {self.UBS_RED};
            }}
            
            .metadata-value {{
                color: {self.UBS_GRAY};
            }}
            
            .document-body {{
                margin-top: 30px;
            }}
            
            /* Headings */
            h2 {{
                color: {self.UBS_RED};
                font-size: 1.8rem;
                margin: 30px 0 15px 0;
                padding-bottom: 10px;
                border-bottom: 2px solid {self.UBS_LIGHT_GRAY};
            }}
            
            h3 {{
                color: {self.UBS_DARK_RED};
                font-size: 1.4rem;
                margin: 25px 0 12px 0;
            }}
            
            h4 {{
                color: {self.UBS_GRAY};
                font-size: 1.2rem;
                margin: 20px 0 10px 0;
            }}
            
            /* Paragraphs */
            p {{
                margin: 15px 0;
                line-height: 1.8;
                text-align: justify;
            }}
            
            /* Color-coded content boxes */
            .important {{
                background-color: #FFE6E6;
                border-left: 4px solid {self.COLOR_IMPORTANT};
                padding: 20px;
                margin: 20px 0;
                border-radius: 5px;
            }}
            
            .important::before {{
                content: "⚠ IMPORTANT: ";
                font-weight: bold;
                color: {self.COLOR_IMPORTANT};
                font-size: 1.1rem;
            }}
            
            .warning {{
                background-color: #FFF3E0;
                border-left: 4px solid {self.COLOR_WARNING};
                padding: 20px;
                margin: 20px 0;
                border-radius: 5px;
            }}
            
            .warning::before {{
                content: "⚡ WARNING: ";
                font-weight: bold;
                color: {self.COLOR_WARNING};
                font-size: 1.1rem;
            }}
            
            .tip {{
                background-color: #FFFACD;
                border-left: 4px solid {self.COLOR_TIP};
                padding: 20px;
                margin: 20px 0;
                border-radius: 5px;
            }}
            
            .tip::before {{
                content: "💡 TIP: ";
                font-weight: bold;
                color: #DAA520;
                font-size: 1.1rem;
            }}
            
            .success {{
                background-color: #E8F5E9;
                border-left: 4px solid {self.COLOR_SUCCESS};
                padding: 20px;
                margin: 20px 0;
                border-radius: 5px;
            }}
            
            .success::before {{
                content: "✓ BEST PRACTICE: ";
                font-weight: bold;
                color: {self.COLOR_SUCCESS};
                font-size: 1.1rem;
            }}
            
            .info {{
                background-color: #E3F2FD;
                border-left: 4px solid {self.COLOR_INFO};
                padding: 20px;
                margin: 20px 0;
                border-radius: 5px;
            }}
            
            .info::before {{
                content: "ℹ INFO: ";
                font-weight: bold;
                color: {self.COLOR_INFO};
                font-size: 1.1rem;
            }}
            
            .note {{
                background-color: #F5F5F5;
                border-left: 4px solid {self.COLOR_NOTE};
                padding: 20px;
                margin: 20px 0;
                border-radius: 5px;
            }}
            
            .note::before {{
                content: "📝 NOTE: ";
                font-weight: bold;
                color: {self.COLOR_NOTE};
                font-size: 1.1rem;
            }}
            
            /* Lists */
            ul, ol {{
                margin: 20px 0;
                padding-left: 40px;
            }}
            
            li {{
                margin: 12px 0;
                line-height: 1.8;
            }}
            
            /* Nested lists */
            ul ul, ol ol, ul ol, ol ul {{
                margin: 8px 0;
            }}
            
            /* Code blocks */
            .code-block {{
                background: #2D2D2D;
                color: #F8F8F2;
                padding: 25px;
                border-radius: 5px;
                overflow-x: auto;
                margin: 20px 0;
                font-family: 'Courier New', monospace;
                font-size: 0.95rem;
                line-height: 1.6;
            }}
            
            code {{
                background: #F4F4F4;
                padding: 3px 8px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
                color: {self.UBS_DARK_RED};
            }}
            
            pre {{
                white-space: pre-wrap;
                word-wrap: break-word;
            }}
            
            /* Images */
            .image-container {{
                margin: 30px 0;
                text-align: center;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                border: 1px solid #e0e0e0;
            }}
            
            .image-container img {{
                max-width: 100%;
                height: auto;
                border-radius: 5px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .image-caption {{
                margin-top: 12px;
                color: {self.UBS_GRAY};
                font-style: italic;
                font-size: 0.9rem;
            }}
            
            /* Tables */
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 25px 0;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            
            th {{
                background: {self.UBS_RED};
                color: white;
                padding: 15px;
                text-align: left;
                font-weight: 600;
            }}
            
            td {{
                padding: 12px 15px;
                border-bottom: 1px solid #ddd;
            }}
            
            tr:hover {{
                background-color: {self.UBS_LIGHT_GRAY};
            }}
            
            /* Footer */
            .footer {{
                background: {self.UBS_LIGHT_GRAY};
                border-top: 3px solid {self.UBS_RED};
                padding: 30px;
                text-align: center;
                color: {self.UBS_GRAY};
            }}
            
            .footer-logo {{
                margin-bottom: 15px;
            }}
            
            .footer-team {{
                color: {self.UBS_RED};
                font-weight: 600;
                margin-top: 10px;
            }}
            
            /* Print styles */
            @media print {{
                body {{
                    background: white;
                    padding: 0;
                }}
                .container {{
                    box-shadow: none;
                }}
                .header {{
                    background: {self.UBS_RED};
                }}
            }}
            
            @page {{
                margin: 2cm;
            }}
        </style>
        """
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """Convert image file to base64 string"""
        try:
            with open(image_path, 'rb') as image_file:
                encoded = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded
        except Exception as e:
            print(f"Error encoding image {image_path}: {e}")
            return ""
    
    def _classify_and_format_content(self, text: str) -> str:
        """Classify content and wrap with appropriate color-coded div"""
        if not text or not text.strip():
            return ""
        
        text = text.strip()
        text_lower = text.lower()
        
        # Check for important keywords
        if any(keyword in text_lower for keyword in ['critical', 'must', 'required', 'mandatory', 'essential', 'important:']):
            return f'<div class="important">{self._escape_html(text)}</div>'
        
        # Check for warnings
        elif any(keyword in text_lower for keyword in ['warning:', 'caution:', 'danger:', 'risk:', 'avoid', 'do not']):
            return f'<div class="warning">{self._escape_html(text)}</div>'
        
        # Check for tips
        elif any(keyword in text_lower for keyword in ['tip:', 'hint:', 'suggestion:', 'consider', 'recommend', 'helpful']):
            return f'<div class="tip">{self._escape_html(text)}</div>'
        
        # Check for best practices
        elif any(keyword in text_lower for keyword in ['best practice:', 'recommended:', 'should', 'optimal', 'ideal']):
            return f'<div class="success">{self._escape_html(text)}</div>'
        
        # Check for notes
        elif any(keyword in text_lower for keyword in ['note:', 'remember:', 'keep in mind', 'important to note']):
            return f'<div class="note">{self._escape_html(text)}</div>'
        
        # Check for info
        elif any(keyword in text_lower for keyword in ['info:', 'information:', 'fyi:', 'reference:', 'see also']):
            return f'<div class="info">{self._escape_html(text)}</div>'
        
        # Check for code blocks
        elif '```' in text or text.startswith('    ') or text.startswith('\t'):
            code_content = text.replace('```', '').strip()
            return f'<div class="code-block"><pre>{self._escape_html(code_content)}</pre></div>'
        
        # Check for headings
        elif text.startswith('# '):
            return f'<h2>{self._escape_html(text[2:])}</h2>'
        elif text.startswith('## '):
            return f'<h3>{self._escape_html(text[3:])}</h3>'
        elif text.startswith('### '):
            return f'<h4>{self._escape_html(text[4:])}</h4>'
        
        # Regular paragraph
        else:
            return f'<p>{self._escape_html(text)}</p>'
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        if not isinstance(text, str):
            text = str(text)
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
    
    def generate_html(self, analysis_results: Dict[str, Any], output_path: str = None) -> str:
        """
        Generate HTML document showing only improved content with images.
        
        Args:
            analysis_results: Dictionary containing analysis results
            output_path: Optional path to save HTML file
            
        Returns:
            HTML string
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doc_name = analysis_results.get('document_name', 'Unknown Document')
        workflow_mode = analysis_results.get('workflow_mode', 'unknown')
        
        html_parts = []
        
        # HTML Header
        html_parts.append(f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KAT - {doc_name}</title>
    {self._get_css_styles()}
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-logo">
                <div class="header-logo-text">UBS</div>
            </div>
            <h1>Knowledge Analysis Tool</h1>
            <p class="subtitle">Enhanced Document Report</p>
        </div>
        
        <!-- Content -->
        <div class="content">
            <h1 class="document-title">{self._escape_html(doc_name)}</h1>
            
            <!-- Metadata -->
            <div class="metadata">
                <div class="metadata-item">
                    <span class="metadata-label">Analysis Mode:</span>
                    <span class="metadata-value">{workflow_mode}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Generated:</span>
                    <span class="metadata-value">{timestamp}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Generated by:</span>
                    <span class="metadata-value">KAT - UBS AI Engineering Team</span>
                </div>
            </div>
            
            <div class="document-body">
        """)
        
        # Extract and display improved document content
        improved_content = None
        
        # First, check for improved_document
        if 'improved_document' in analysis_results and analysis_results['improved_document']:
            improved_doc = analysis_results['improved_document']
            if isinstance(improved_doc, dict):
                improved_content = improved_doc.get('improved_content')
            else:
                improved_content = improved_doc
        
        # If no improved content, fall back to cleaned content
        if not improved_content and 'cleaned_content' in analysis_results:
            cleaned = analysis_results['cleaned_content']
            if isinstance(cleaned, dict):
                # Reconstruct from cleaned structure
                parts = []
                
                if 'title' in cleaned:
                    parts.append(f"# {cleaned['title']}")
                
                if 'prerequisites' in cleaned and cleaned['prerequisites']:
                    parts.append("## Prerequisites")
                    for prereq in cleaned['prerequisites']:
                        parts.append(f"- {prereq}")
                
                if 'steps' in cleaned and cleaned['steps']:
                    parts.append("## Procedure Steps")
                    for i, step in enumerate(cleaned['steps'], 1):
                        parts.append(f"{i}. {step}")
                
                if 'warnings' in cleaned and cleaned['warnings']:
                    parts.append("## Warnings")
                    for warning in cleaned['warnings']:
                        parts.append(f"WARNING: {warning}")
                
                improved_content = '\n\n'.join(parts)
            else:
                improved_content = str(cleaned)
        
        # If still no content, use raw text
        if not improved_content and 'parsed_content' in analysis_results:
            parsed = analysis_results['parsed_content']
            if isinstance(parsed, dict):
                improved_content = parsed.get('raw_text', '')
            else:
                improved_content = str(parsed)
        
        # Format and display the content
        if improved_content:
            if isinstance(improved_content, str):
                # Split into sections and format
                sections = improved_content.split('\n\n')
                for section in sections:
                    if section.strip():
                        html_parts.append(self._classify_and_format_content(section))
            else:
                html_parts.append(f'<p>{self._escape_html(str(improved_content))}</p>')
        else:
            html_parts.append('<p><em>No content available</em></p>')
        
        # Add images if available
        if 'parsed_content' in analysis_results:
            parsed_content = analysis_results['parsed_content']
            if isinstance(parsed_content, dict) and 'images' in parsed_content:
                images = parsed_content['images']
                
                if images:
                    html_parts.append('<h2>Document Images</h2>')
                    
                    for idx, img_data in enumerate(images, 1):
                        if isinstance(img_data, dict) and 'path' in img_data:
                            img_path = img_data['path']
                            if Path(img_path).exists():
                                base64_img = self._encode_image_to_base64(img_path)
                                if base64_img:
                                    page = img_data.get('page', 'N/A')
                                    html_parts.append(f"""
                                    <div class="image-container">
                                        <img src="data:image/png;base64,{base64_img}" alt="Image {idx}">
                                        <div class="image-caption">Figure {idx} - Page {page}</div>
                                    </div>
                                    """)
        
        # Close content and add footer
        html_parts.append("""
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <div class="footer-logo">
                <svg width="60" height="60" viewBox="0 0 60 60">
                    <rect width="60" height="60" fill="#E60000" rx="5"/>
                    <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" 
                          font-family="Arial" font-size="28" font-weight="bold" fill="white">UBS</text>
                </svg>
            </div>
            <div>
                <strong>Knowledge Analysis Tool (KAT)</strong><br>
                Generated by UBS Technology Innovation Team<br>
                <div class="footer-team">
                    AI Engineering & Automation Excellence Team<br>
                    © 2026 UBS Group AG. All rights reserved.
                </div>
            </div>
        </div>
    </div>
</body>
</html>
        """)
        
        html_content = '\n'.join(html_parts)
        
        # Save to file if path provided
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"HTML report saved to: {output_path}")
        
        return html_content


# Convenience function
def generate_html_report(analysis_results: Dict[str, Any], output_path: str) -> str:
    """
    Generate simplified HTML report with only improved content and images.
    
    Args:
        analysis_results: Analysis results dictionary
        output_path: Path to save HTML file
        
    Returns:
        HTML content string
    """
    generator = HTMLDocumentGenerator()
    return generator.generate_html(analysis_results, output_path)
