    # ----------------------
    # AGENT 1: PDF parsing (UPDATED TO STORE IMAGES)
    # ----------------------

    async def _parse_document_agent(self, state: WorkflowState) -> WorkflowState:
        print("🔍 Document Parser Agent...")
        combined_content = await self._extract_content_by_page(state['pdf_path'])

        state['parsed_content'] = {
            'combined_text': combined_content['full_text'],
            'page_breakdown': combined_content['pages'],
            'total_pages': combined_content['total_pages'],
            'processing_summary': combined_content['summary'],
            'image_analysis': combined_content.get('image_analysis', []),
            # NEW: list of image metadata with file paths
            'images': combined_content.get('images', [])
        }
        state['current_step'] = 'parsing_complete'
        return state

    async def _extract_content_by_page(self, pdf_path: str) -> Dict[str, Any]:
        """Image analysis is embedded directly into combined_text, and images are saved for HTML."""
        import os
        import io
        from pathlib import Path
        from PIL import Image

        combined_text = ""
        page_details = []
        image_analysis = []
        images: list[dict] = []

        # Create per-document image directory next to the PDF (or adjust as you like)
        pdf_path_obj = Path(pdf_path)
        image_root = pdf_path_obj.parent / "kat_images"
        image_root.mkdir(parents=True, exist_ok=True)
        image_dir = image_root / pdf_path_obj.stem
        image_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            text_dict = page.get_text("dict", sort=True)
            page_text_content = self._extract_text_from_page_dict(text_dict)

            image_list = page.get_images()
            page_multimodal_content = ""
            page_image_analysis = []
            page_image_meta = []

            if image_list:
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)

                        # Save image to disk (for HTML generator)
                        # Convert to PNG; for non-RGB, transform first.
                        if pix.n - pix.alpha < 4:
                            # RGB(A) or grayscale
                            img_bytes = pix.tobytes("png")
                        else:
                            # CMYK and others: convert to RGB first
                            pix_converted = fitz.Pixmap(fitz.csRGB, pix)
                            img_bytes = pix_converted.tobytes("png")
                            pix_converted = None

                        # Persist the image file
                        img_filename = f"page_{page_num + 1}_img_{img_index + 1}.png"
                        img_path = image_dir / img_filename

                        # Use Pillow to write bytes to PNG file
                        image_pil = Image.open(io.BytesIO(img_bytes))
                        image_pil.save(str(img_path))

                        # Store metadata for HTML generator
                        page_image_meta.append({
                            'path': str(img_path),
                            'page': page_num + 1,
                            'image_index': img_index + 1,
                            'width': image_pil.width,
                            'height': image_pil.height,
                            'mime_type': 'image/png'
                        })

                        # Existing multimodal analysis (unchanged)
                        multimodal_result = await self._perform_multimodal_analysis(
                            img_bytes, page_num + 1, img_index + 1
                        )

                        image_block = f"\n\n[IMAGE_{img_index + 1}_ANALYSIS]:\n"
                        image_block += f"Description: {multimodal_result['description']}\n"
                        image_block += f"Purpose: {multimodal_result['purpose']}\n"
                        image_block += f"Automation Relevance: {multimodal_result['automation_relevance']}\n"
                        if multimodal_result['extracted_text'].strip():
                            image_block += f"Extracted Text: {multimodal_result['extracted_text']}\n"
                        else:
                            image_block += "Extracted Text: No text detected in image\n"
                        image_block += f"[END_IMAGE_{img_index + 1}_ANALYSIS]\n\n"

                        page_multimodal_content += image_block
                        page_image_analysis.append({
                            'page': page_num + 1,
                            'image_index': img_index + 1,
                            'extracted_text': multimodal_result['extracted_text'],
                            'image_description': multimodal_result['description'],
                            'purpose': multimodal_result['purpose'],
                            'automation_relevance': multimodal_result['automation_relevance']
                        })

                        pix = None
                    except Exception as e:
                        page_multimodal_content += f"\n[IMAGE_{img_index + 1}_ERROR]: {e}\n"

            page_combined = f"\n--- PAGE {page_num + 1} ---\n"
            page_combined += page_text_content

            if page_multimodal_content:
                page_combined += "\n" + page_multimodal_content

            page_combined += f"\n--- END PAGE {page_num + 1} ---\n\n"

            combined_text += page_combined

            page_details.append({
                'page_number': page_num + 1,
                'text_length': len(page_text_content),
                'image_count': len(image_list),
                'multimodal_content_length': len(page_multimodal_content),
                'combined_length': len(page_combined)
            })
            image_analysis.extend(page_image_analysis)
            images.extend(page_image_meta)

        doc.close()

        summary = {
            'total_text_length': len(combined_text),
            'pages_with_images': sum(1 for p in page_details if p['image_count'] > 0),
            'total_images': sum(p['image_count'] for p in page_details),
            'pages_with_multimodal_content': sum(1 for p in page_details if p['multimodal_content_length'] > 0),
            'image_analysis_count': len(image_analysis)
        }

        return {
            'full_text': combined_text,
            'pages': page_details,
            'total_pages': total_pages,
            'summary': summary,
            'image_analysis': image_analysis,
            # NEW: images metadata list for HTML generator
            'images': images
        }

    def _extract_text_from_page_dict(self, text_dict: Dict) -> str:
        text_content = ""
        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                    if line_text.strip():
                        text_content += line_text + "\n"
        return text_content

    async def _perform_multimodal_analysis(self, image_data: bytes, page_num: int, img_num: int) -> Dict[str, str]:
        """Multimodal image analysis"""
        try:
            img_base64 = base64.b64encode(image_data).decode('utf-8')
            multimodal_prompt = f"""
            Analyze this image from page {page_num}, image {img_num} of a technical/business document.

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
