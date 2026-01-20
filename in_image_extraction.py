import os
import base64
from pathlib import Path
import tempfile

async def _parse_document_agent(self, state: WorkflowState) -> WorkflowState:
    print("🔍 Document Parser Agent...")
    combined_content = await self._extract_content_by_page(state['pdf_path'])

    state['parsed_content'] = {
        'combined_text': combined_content['full_text'],
        'page_breakdown': combined_content['pages'],
        'total_pages': combined_content['total_pages'],
        'processing_summary': combined_content['summary'],
        'image_analysis': combined_content.get('image_analysis', []),
        'image_files': combined_content.get('image_files', [])  # ✅ NEW: Disk file paths
    }
    state['current_step'] = 'parsing_complete'
    return state

async def _extract_content_by_page(self, pdf_path: str) -> Dict[str, Any]:
    """Extract content with images at EXACT positions + save to disk"""
    combined_text = ""
    page_details = []
    image_analysis = []
    image_files = []  # ✅ NEW: Track saved image files
    
    # Create temp directory for images
    temp_dir = Path(tempfile.mkdtemp(prefix="kat_images_"))
    temp_dir.mkdir(exist_ok=True)
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        
        # ✅ Get text blocks WITH POSITIONS
        text_dict = page.get_text("dict", sort=True)
        text_blocks = self._extract_text_blocks_with_positions(text_dict)
        
        # ✅ Get images WITH POSITIONS
        image_list = page.get_images()
        page_images_with_pos = []
        
        if image_list:
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    # ✅ Get exact image position
                    img_rects = page.get_image_rects(xref)
                    if img_rects:
                        rect = img_rects[0]
                        y_position = rect.y0  # Top position
                        
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n - pix.alpha < 4:
                            img_data = pix.tobytes("png")
                            img_base64 = base64.b64encode(img_data).decode('utf-8')
                            
                            # ✅ SAVE TO DISK
                            img_filename = f"page_{page_num+1}_img_{img_index+1}.png"
                            img_path = temp_dir / img_filename
                            with open(img_path, 'wb') as f:
                                f.write(img_data)
                            
                            multimodal_result = await self._perform_multimodal_analysis(
                                img_data, page_num + 1, img_index + 1
                            )

                            # ✅ Store complete image data
                            image_data = {
                                'page': page_num + 1,
                                'image_index': img_index + 1,
                                'y_position': y_position,
                                'rect': [rect.x0, rect.y0, rect.x1, rect.y1],
                                'file_path': str(img_path),  # ✅ Disk path
                                'base64': img_base64,
                                'extracted_text': multimodal_result['extracted_text'],
                                'image_description': multimodal_result['description'],
                                'purpose': multimodal_result['purpose'],
                                'automation_relevance': multimodal_result['automation_relevance']
                            }
                            
                            page_images_with_pos.append(image_data)
                            image_analysis.append(image_data)
                            image_files.append(image_data)
                            
                            pix = None
                except Exception as e:
                    print(f"⚠️ Image {img_index+1} error: {e}")

        # ✅ MERGE TEXT + IMAGES BY POSITION
        page_content = self._merge_content_by_position(text_blocks, page_images_with_pos)
        
        page_combined = f"\n--- PAGE {page_num + 1} ---\n"
        page_combined += page_content
        page_combined += f"\n--- END PAGE {page_num + 1} ---\n\n"
        combined_text += page_combined

        page_details.append({
            'page_number': page_num + 1,
            'text_length': len(page_content.split('\n[IMAGE_')[0]),  # Text only
            'image_count': len(page_images_with_pos),
            'multimodal_content_length': sum(len(str(img)) for img in page_images_with_pos),
            'combined_length': len(page_content)
        })

    doc.close()
    
    summary = {
        'total_text_length': len(combined_text),
        'pages_with_images': sum(1 for p in page_details if p['image_count'] > 0),
        'total_images': len(image_files),
        'image_analysis_count': len(image_analysis),
        'temp_image_dir': str(temp_dir)  # ✅ Track temp dir for cleanup
    }

    return {
        'full_text': combined_text,
        'pages': page_details,
        'total_pages': total_pages,
        'summary': summary,
        'image_analysis': image_analysis,
        'image_files': image_files  # ✅ NEW
    }

def _extract_text_blocks_with_positions(self, text_dict: Dict) -> List[Dict]:
    """Extract text blocks with their Y positions"""
    text_blocks = []
    for block in text_dict.get("blocks", []):
        if "lines" in block:
            block_text = ""
            bbox = block.get('bbox', [0, 0, 0, 0])  # [x0, y0, x1, y1]
            for line in block["lines"]:
                line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                if line_text.strip():
                    block_text += line_text + "\n"
            
            if block_text.strip():
                text_blocks.append({
                    'text': block_text.strip(),
                    'y_position': bbox[1],  # Top Y position
                    'bbox': bbox
                })
    return text_blocks

def _merge_content_by_position(self, text_blocks: List[Dict], images: List[Dict]) -> str:
    """Merge text and images in document reading order by Y position"""
    all_elements = []
    
    # Add text blocks
    for text_block in text_blocks:
        all_elements.append({
            'type': 'text',
            'y_position': text_block['y_position'],
            'content': text_block['text']
        })
    
    # Add images
    for img in images:
        all_elements.append({
            'type': 'image',
            'y_position': img['y_position'],
            'content': f"\n\n[IMAGE_{img['image_index']}_ANALYSIS]:\nDescription: {img['image_description']}\nPurpose: {img['purpose']}\nAutomation Relevance: {img['automation_relevance']}\nExtracted Text: {img['extracted_text']}\n[END_IMAGE_{img['image_index']}_ANALYSIS]\n\n"
        })
    
    # ✅ Sort by Y position (top to bottom)
    all_elements.sort(key=lambda x: x['y_position'])
    
    # Build final content
    page_content = ""
    for element in all_elements:
        page_content += element['content']
    
    return page_content

def _extract_text_from_page_dict(self, text_dict: Dict) -> str:
    """Fallback - unchanged"""
    text_content = ""
    for block in text_dict.get("blocks", []):
        if "lines" in block:
            for line in block["lines"]:
                line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                if line_text.strip():
                    text_content += line_text + "\n"
    return text_content

async def _perform_multimodal_analysis(self, image_data: bytes, page_num: int, img_num: int) -> Dict[str, str]:
    """Unchanged - your existing function"""
    try:
        img_base64 = base64.b64encode(image_data).decode('utf-8')
        multimodal_prompt = f"""
        Analyze this image from page {page_num}, image {img_num} of a document.

        Return exactly:
        EXTRACTED_TEXT: ...
        IMAGE_DESCRIPTION: ...
        PURPOSE: ...
        AUTOMATION_RELEVANCE: ...
        """
        message_content = [
            {"type": "text", "text": multimodal_prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_base64}", "detail": "high"}
            }
        ]
        resp = await self.llm.ainvoke([HumanMessage(content=message_content)])
        content = (resp.content or "").strip()

        extracted_text = ""
        description = ""
        purpose = ""
        automation_relevance = ""
        current = None
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("EXTRACTED_TEXT:"):
                current = "text"
                extracted_text = line.replace("EXTRACTED_TEXT:", "").strip()
            elif line.startswith("IMAGE_DESCRIPTION:"):
                current = "desc"
                description = line.replace("IMAGE_DESCRIPTION:", "").strip()
            elif line.startswith("PURPOSE:"):
                current = "purpose"
                purpose = line.replace("PURPOSE:", "").strip()
            elif line.startswith("AUTOMATION_RELEVANCE:"):
                current = "relevance"
                automation_relevance = line.replace("AUTOMATION_RELEVANCE:", "").strip()
            elif line and current:
                if current == "text":
                    extracted_text += " " + line
                elif current == "desc":
                    description += " " + line
                elif current == "purpose":
                    purpose += " " + line
                elif current == "relevance":
                    automation_relevance += " " + line

        return {
            "extracted_text": extracted_text.strip(),
            "description": description.strip() or "No description",
            "purpose": purpose.strip() or "No purpose extracted",
            "automation_relevance": automation_relevance.strip() or "No automation relevance extracted"
        }
    except Exception as e:
        return {
            "extracted_text": "",
            "description": f"Error: {e}",
            "purpose": "Analysis failed",
            "automation_relevance": "Analysis failed"
        }
