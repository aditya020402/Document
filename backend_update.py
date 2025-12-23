import asyncio
import re
from typing import Dict, Any, List, TypedDict
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
import fitz  # PyMuPDF
import json
from pathlib import Path
import base64
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import AzureOpenAI

# NEW: Import token tracker
from token_tracker import TokenTracker

# ----------------------
# Utility: Paragraph-based chunking with recursive fallback
# ----------------------

def chunk_text_by_paragraphs(text: str, max_chunk_size: int = 4000, overlap_paragraphs: int = 1) -> List[str]:
    """
    Chunk text based on paragraph boundaries (double newlines).
    Falls back to sentence and word boundaries if paragraphs are too large.
    Includes paragraph overlap for context preservation.
    """
    if not text or len(text) <= max_chunk_size:
        return [text] if text else []
    
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for i, para in enumerate(paragraphs):
        para_length = len(para)
        
        if para_length > max_chunk_size:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_length = 0
            
            sub_chunks = _split_large_paragraph(para, max_chunk_size)
            chunks.extend(sub_chunks)
            continue
        
        if current_length + para_length + 2 > max_chunk_size and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            
            if overlap_paragraphs > 0 and len(current_chunk) > overlap_paragraphs:
                current_chunk = current_chunk[-overlap_paragraphs:]
                current_length = sum(len(p) for p in current_chunk) + (len(current_chunk) - 1) * 2
            else:
                current_chunk = []
                current_length = 0
        
        current_chunk.append(para)
        current_length += para_length + 2
    
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks


def _split_large_paragraph(paragraph: str, max_size: int) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', paragraph)
    
    if len(sentences) == 1 or max(len(s) for s in sentences) > max_size:
        return _split_by_words(paragraph, max_size)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence_length = len(sentence)
        
        if current_length + sentence_length + 1 > max_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_length
        else:
            current_chunk.append(sentence)
            current_length += sentence_length + 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def _split_by_words(text: str, max_size: int) -> List[str]:
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word)
        
        if current_length + word_length + 1 > max_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = word_length
        else:
            current_chunk.append(word)
            current_length += word_length + 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


class WorkflowState(TypedDict):
    pdf_path: str
    parsed_content: Dict[str, Any]
    cleaned_content: Dict[str, Any]
    automation_analysis: Dict[str, Any]
    improved_document: Dict[str, Any]
    similarity_matches: Dict[str, Any]
    automation_commands: Dict[str, Any]
    generated_script: Dict[str, Any]
    messages: List[Any]
    current_step: str
    workflow_mode: str


class DocumentAutomationWorkflow:
    def __init__(self, db_config: Dict[str, str] = None, azure_embedding_config: Dict[str, str] = None):
        # LLM (GPT‑4o mini on Azure)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            azure_endpoint="your-azure-endpoint",
            api_key="your-api-key",
            api_version="2024-07-18"
        )

        # pg / pgvector config
        self.db_config = db_config or {
            'dbname': 'automation_db',
            'user': 'your_username',
            'password': 'your_password',
            'host': 'localhost',
            'port': '5432'
        }

        # Azure embeddings (Ada small)
        self.azure_embedding_config = azure_embedding_config or {
            'api_key': 'your-azure-api-key',
            'api_version': '2023-05-15',
            'endpoint': 'https://your-resource.openai.azure.com/',
            'embedding_deployment': 'text-embedding-ada-002'
        }

        try:
            self.embedding_client = AzureOpenAI(
                api_key=self.azure_embedding_config['api_key'],
                api_version=self.azure_embedding_config['api_version'],
                azure_endpoint=self.azure_embedding_config['endpoint']
            )
            self.embedding_enabled = True
        except Exception as e:
            print(f"⚠️ Could not init embedding client: {e}")
            self.embedding_enabled = False

        # NEW: Initialize token tracker
        self.token_tracker = TokenTracker(db_path="token_usage.db")

        # Build both workflows
        self.full_workflow = self._build_full_workflow()
        self.content_workflow = self._build_content_workflow()

    def _build_full_workflow(self) -> StateGraph:
        """Full automation workflow with all 6 agents"""
        workflow = StateGraph(WorkflowState)

        workflow.add_node("parse_document", self._parse_document_agent)
        workflow.add_node("clean_text", self._text_cleaning_agent)
        workflow.add_node("analyze_automation", self._enhanced_automation_analysis_agent)
        workflow.add_node("similarity_matching", self._similarity_matching_agent)
        workflow.add_node("automation_commands", self._automation_commands_agent)
        workflow.add_node("generate_script", self._script_generation_agent)

        workflow.add_edge(START, "parse_document")
        workflow.add_edge("parse_document", "clean_text")
        workflow.add_edge("clean_text", "analyze_automation")
        workflow.add_edge("analyze_automation", "similarity_matching")
        workflow.add_edge("similarity_matching", "automation_commands")
        workflow.add_edge("automation_commands", "generate_script")
        workflow.add_edge("generate_script", END)

        return workflow.compile()

    def _build_content_workflow(self) -> StateGraph:
        """Content quality workflow"""
        workflow = StateGraph(WorkflowState)

        workflow.add_node("parse_document", self._parse_document_agent)
        workflow.add_node("clean_text", self._text_cleaning_agent)
        workflow.add_node("analyze_content_quality", self._content_quality_scoring_agent)
        workflow.add_node("improve_content", self._content_improvement_agent)

        workflow.add_edge(START, "parse_document")
        workflow.add_edge("parse_document", "clean_text")
        workflow.add_edge("clean_text", "analyze_content_quality")
        workflow.add_edge("analyze_content_quality", "improve_content")
        workflow.add_edge("improve_content", END)

        return workflow.compile()

    # ----------------------
    # AGENT 1: PDF parsing with token tracking
    # ----------------------

    async def _parse_document_agent(self, state: WorkflowState) -> WorkflowState:
        print("🔍 Document Parser Agent...")
        combined_content = await self._extract_content_by_page(state['pdf_path'])

        state['parsed_content'] = {
            'combined_text': combined_content['full_text'],
            'page_breakdown': combined_content['pages'],
            'total_pages': combined_content['total_pages'],
            'processing_summary': combined_content['summary'],
            'image_analysis': combined_content.get('image_analysis', [])
        }
        state['current_step'] = 'parsing_complete'
        return state

    async def _extract_content_by_page(self, pdf_path: str) -> Dict[str, Any]:
        """Image analysis is embedded directly into combined_text"""
        combined_text = ""
        page_details = []
        image_analysis = []

        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            text_dict = page.get_text("dict", sort=True)
            page_text_content = self._extract_text_from_page_dict(text_dict)

            image_list = page.get_images()
            page_multimodal_content = ""
            page_image_analysis = []

            if image_list:
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n - pix.alpha < 4:
                            img_data = pix.tobytes("png")
                            multimodal_result = await self._perform_multimodal_analysis(
                                img_data, page_num + 1, img_index + 1
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
            'image_analysis': image_analysis
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
        """Multimodal image analysis WITH TOKEN TRACKING"""
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
            
            # NEW: Track tokens
            self.token_tracker.track_api_call("multimodal_image_analysis", resp, "gpt-4o-mini")
            
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

    # ----------------------
    # AGENT 2: Cleaning with token tracking
    # ----------------------

    async def _text_cleaning_agent(self, state: WorkflowState) -> WorkflowState:
        print("🧹 Text Cleaning Agent...")
        raw_text = state['parsed_content']['combined_text']

        cleaned_text_basic = self._basic_text_cleaning(raw_text)
        filtered_text = await self._ai_content_filtering(cleaned_text_basic)
        final_text = self._remove_headers_footers(filtered_text)
        structured_content = await self._extract_key_sections(final_text)

        cleaning_stats = {
            'original_length': len(raw_text),
            'cleaned_length': len(final_text),
            'reduction_percentage': round(
                (len(raw_text) - len(final_text)) / len(raw_text) * 100, 2
            ) if len(raw_text) > 0 else 0,
            'sections_identified': len([s for s in structured_content['sections'].values() if s]),
            'key_phrases_found': len(structured_content.get('key_phrases', []))
        }

        state['cleaned_content'] = {
            'cleaned_text': final_text,
            'structured_content': structured_content,
            'image_analysis': state['parsed_content'].get('image_analysis', []),
            'cleaning_stats': cleaning_stats,
            'removed_elements': {
                'headers_footers': True,
                'page_numbers': True,
                'ocr_noise': True,
                'repetitive_content': True
            }
        }
        state['current_step'] = 'cleaning_complete'
        return state

    def _basic_text_cleaning(self, text: str) -> str:
        text = re.sub(r'--- PAGE \d+ ---', '', text)
        text = re.sub(r'--- END PAGE \d+ ---', '', text)
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()

    async def _ai_content_filtering(self, text: str) -> str:
        """WITH TOKEN TRACKING"""
        chunks = chunk_text_by_paragraphs(text, max_chunk_size=4000, overlap_paragraphs=1)
        cleaned_chunks = []
        
        print(f"🧹 Cleaning {len(chunks)} sections...")
        
        for i, chunk in enumerate(chunks):
            prompt = f"""
            You are cleaning a document.

            Tasks:
            - Remove headers, footers, boilerplate, page numbers and OCR noise.
            - **IMPORTANT: Keep ALL [IMAGE_X_ANALYSIS] blocks exactly as they are.**
            - Keep all meaningful content, descriptions, data, and information.
            - Preserve order and detail. Do NOT summarize.

            Return ONLY the cleaned text.

            DOCUMENT SECTION:
            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            # NEW: Track tokens
            self.token_tracker.track_api_call("text_cleaning", resp, "gpt-4o-mini")
            
            cleaned_chunks.append((resp.content or "").strip())
        
        return "\n\n".join(cleaned_chunks).strip()

    def _remove_headers_footers(self, text: str) -> str:
        lines = text.split("\n")
        if len(lines) < 10:
            return text

        line_counts: Dict[str, int] = {}
        for line in lines:
            if '[IMAGE_' in line or '[END_IMAGE_' in line:
                continue
            
            clean = re.sub(r'\d+', 'NUM', line.strip())
            if 5 < len(clean) < 80:
                line_counts[clean] = line_counts.get(clean, 0) + 1

        repetitive = {ln for ln, c in line_counts.items() if c >= 3}
        filtered = []
        for line in lines:
            if '[IMAGE_' in line or '[END_IMAGE_' in line or 'Description:' in line or 'Purpose:' in line:
                filtered.append(line)
                continue
            
            clean = re.sub(r'\d+', 'NUM', line.strip())
            if clean not in repetitive:
                filtered.append(line)
        return "\n".join(filtered)

    async def _extract_key_sections(self, text: str) -> Dict[str, Any]:
        sentences = re.split(r'[.!?]+', text)
        sections = {
            'process_descriptions': [],
            'task_instructions': [],
            'data_definitions': [],
            'decision_rules': []
        }

        for s in sentences:
            s_clean = s.strip()
            if len(s_clean) < 10:
                continue
            low = s_clean.lower()
            if any(w in low for w in ['process', 'workflow', 'procedure', 'steps', 'method']):
                sections['process_descriptions'].append(s_clean)
            if any(w in low for w in ['task', 'activity', 'operation', 'action', 'function']):
                sections['task_instructions'].append(s_clean)
            if any(w in low for w in ['data', 'information', 'input', 'output', 'field', 'form']):
                sections['data_definitions'].append(s_clean)
            if any(w in low for w in ['if', 'when', 'condition', 'criteria', 'rule']):
                sections['decision_rules'].append(s_clean)

        key_phrases = await self._extract_ai_key_phrases(text)

        return {
            'sections': sections,
            'key_phrases': key_phrases,
            'relevant_sentences': [s for s in sentences if len(s.strip()) > 10]
        }

    async def _extract_ai_key_phrases(self, text: str) -> List[str]:
        """WITH TOKEN TRACKING"""
        chunks = chunk_text_by_paragraphs(text, max_chunk_size=3000, overlap_paragraphs=1)
        phrases: List[str] = []

        for i, chunk in enumerate(chunks):
            prompt = f"""
            From this document, extract 5–10 key phrases that are
            most important (technical terms, concepts, topics, important elements).

            Return ONLY a comma-separated list of phrases.

            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            # NEW: Track tokens
            self.token_tracker.track_api_call("key_phrase_extraction", resp, "gpt-4o-mini")
            
            raw = (resp.content or "").strip()
            for item in raw.split(","):
                p = item.strip().strip('"\'')
                if 2 < len(p) < 80:
                    phrases.append(p)

        seen = set()
        out = []
        for p in phrases:
            key = p.lower()
            if key not in seen:
                seen.add(key)
                out.append(p)
        return out[:30]

    # ----------------------
    # AGENT 3A: Content Quality Scoring with token tracking
    # ----------------------

    async def _content_quality_scoring_agent(self, state: WorkflowState) -> WorkflowState:
        print("📊 Content Quality Scoring Agent...")
        cleaned_text = state['cleaned_content']['cleaned_text']

        quality_scores = await self._analyze_content_quality_dimensions(cleaned_text)
        quality_issues = await self._extract_content_quality_issues(cleaned_text)
        overall_quality = self._calculate_content_quality_score(quality_scores, quality_issues)

        state['automation_analysis'] = {
            'quality_scores': quality_scores,
            'quality_issues': quality_issues,
            'overall_quality': overall_quality,
            'workflow_mode': 'content_improvement'
        }
        
        state['similarity_matches'] = {'skipped': True, 'reason': 'Content improvement mode'}
        state['automation_commands'] = {'skipped': True, 'reason': 'Content improvement mode'}
        state['generated_script'] = {'skipped': True, 'reason': 'Content improvement mode'}
        
        state['current_step'] = 'content_quality_analysis_complete'
        return state

    async def _analyze_content_quality_dimensions(self, text: str) -> Dict[str, Any]:
        """WITH TOKEN TRACKING"""
        chunks = chunk_text_by_paragraphs(text, max_chunk_size=3500, overlap_paragraphs=1)
        chunk_scores = []
        
        print(f"📊 Analyzing content quality across 6 dimensions...")
        
        for idx, chunk in enumerate(chunks):
            chunk_length = len(chunk)
            analysis_prompt = f"""
            You are a content quality expert analyzing a general document (NOT for automation).
            
            Evaluate this document section on 6 quality dimensions (0–10 scale):

            1. **Clarity** (0-10): Is the language clear, unambiguous, and easy to understand?
            2. **Completeness** (0-10): Does it cover all necessary information thoroughly?
            3. **Accuracy** (0-10): Are facts, data, and statements precise and correct?
            4. **Consistency** (0-10): Is terminology, style, and formatting uniform?
            5. **Readability** (0-10): Is it easy to read with appropriate sentence length and structure?
            6. **Organization** (0-10): Is content logically structured and well-organized?

            Return JSON:
            {{
                "clarity_score": <0-10>,
                "clarity_reasoning": "<why this score>",
                "completeness_score": <0-10>,
                "completeness_reasoning": "<why this score>",
                "accuracy_score": <0-10>,
                "accuracy_reasoning": "<why this score>",
                "consistency_score": <0-10>,
                "consistency_reasoning": "<why this score>",
                "readability_score": <0-10>,
                "readability_reasoning": "<why this score>",
                "organization_score": <0-10>,
                "organization_reasoning": "<why this score>",
                "chunk_weight": {chunk_length}
            }}

            DOCUMENT CONTENT:
            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=analysis_prompt)])
            
            # NEW: Track tokens
            self.token_tracker.track_api_call("content_quality_dimension_analysis", resp, "gpt-4o-mini")
            
            try:
                chunk_analysis = json.loads(resp.content)
                chunk_analysis['chunk_weight'] = chunk_length
                chunk_scores.append(chunk_analysis)
            except Exception as e:
                print(f"⚠️ Error in quality analysis: {e}")
                chunk_scores.append({
                    "clarity_score": 5, "clarity_reasoning": "Error in analysis",
                    "completeness_score": 5, "completeness_reasoning": "Error in analysis",
                    "accuracy_score": 5, "accuracy_reasoning": "Error in analysis",
                    "consistency_score": 5, "consistency_reasoning": "Error in analysis",
                    "readability_score": 5, "readability_reasoning": "Error in analysis",
                    "organization_score": 5, "organization_reasoning": "Error in analysis",
                    "chunk_weight": chunk_length
                })
        
        total_weight = sum(c['chunk_weight'] for c in chunk_scores)
        
        def weighted_avg(metric: str) -> float:
            return sum(c[metric] * c['chunk_weight'] for c in chunk_scores) / total_weight
        
        def synthesize_reasoning(metric: str) -> str:
            all_reasonings = [c[metric] for c in chunk_scores if "Error" not in c[metric]]
            if not all_reasonings:
                return "Analysis could not be completed."
            if len(all_reasonings) == 1:
                return all_reasonings[0]
            return " ".join(all_reasonings)[:600]
        
        recommendations_prompt = f"""
        Based on content quality analysis with these scores:
        - Clarity: {weighted_avg('clarity_score'):.1f}/10
        - Completeness: {weighted_avg('completeness_score'):.1f}/10
        - Accuracy: {weighted_avg('accuracy_score'):.1f}/10
        - Consistency: {weighted_avg('consistency_score'):.1f}/10
        - Readability: {weighted_avg('readability_score'):.1f}/10
        - Organization: {weighted_avg('organization_score'):.1f}/10

        Provide:
        1. Top 5 improvement recommendations
        2. Critical issues
        3. Quick wins

        Return JSON:
        {{
            "improvement_recommendations": ["rec1", "rec2", "rec3", "rec4", "rec5"],
            "critical_issues": ["issue1", "issue2"],
            "quick_wins": ["win1", "win2", "win3"]
        }}
        """
        
        rec_resp = await self.llm.ainvoke([HumanMessage(content=recommendations_prompt)])
        
        # NEW: Track tokens
        self.token_tracker.track_api_call("content_quality_recommendations", rec_resp, "gpt-4o-mini")
        
        try:
            recommendations = json.loads(rec_resp.content)
        except:
            recommendations = {
                "improvement_recommendations": ["Improve clarity", "Add missing details", "Enhance organization"],
                "critical_issues": ["Vague terminology", "Missing sections"],
                "quick_wins": ["Fix typos", "Add headings", "Clarify statements"]
            }
        
        return {
            "clarity_score": round(weighted_avg('clarity_score'), 1),
            "clarity_reasoning": synthesize_reasoning('clarity_reasoning'),
            "completeness_score": round(weighted_avg('completeness_score'), 1),
            "completeness_reasoning": synthesize_reasoning('completeness_reasoning'),
            "accuracy_score": round(weighted_avg('accuracy_score'), 1),
            "accuracy_reasoning": synthesize_reasoning('accuracy_reasoning'),
            "consistency_score": round(weighted_avg('consistency_score'), 1),
            "consistency_reasoning": synthesize_reasoning('consistency_reasoning'),
            "readability_score": round(weighted_avg('readability_score'), 1),
            "readability_reasoning": synthesize_reasoning('readability_reasoning'),
            "organization_score": round(weighted_avg('organization_score'), 1),
            "organization_reasoning": synthesize_reasoning('organization_reasoning'),
            "improvement_recommendations": recommendations.get('improvement_recommendations', []),
            "critical_issues": recommendations.get('critical_issues', []),
            "quick_wins": recommendations.get('quick_wins', []),
            "analysis_method": "comprehensive_content_quality_analysis"
        }

    async def _extract_content_quality_issues(self, text: str) -> Dict[str, Any]:
        """WITH TOKEN TRACKING"""
        chunks = chunk_text_by_paragraphs(text, max_chunk_size=4000, overlap_paragraphs=1)
        aggregated = {
            "vague_terms": [],
            "unclear_statements": [],
            "missing_details": [],
            "inconsistencies": [],
            "grammar_issues": [],
            "redundancies": []
        }

        print(f"🔍 Extracting quality issues...")

        for idx, chunk in enumerate(chunks):
            prompt = f"""
            Analyze this document section for content quality issues:

            - "vague_terms": ambiguous or imprecise terminology
            - "unclear_statements": confusing or poorly worded sentences
            - "missing_details": places needing more information
            - "inconsistencies": contradictions or conflicting information
            - "grammar_issues": grammatical errors or awkward phrasing
            - "redundancies": repetitive or redundant content

            Return JSON ONLY:
            {{
              "vague_terms": ["..."],
              "unclear_statements": ["..."],
              "missing_details": ["..."],
              "inconsistencies": ["..."],
              "grammar_issues": ["..."],
              "redundancies": ["..."]
            }}

            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            # NEW: Track tokens
            self.token_tracker.track_api_call("content_quality_issue_extraction", resp, "gpt-4o-mini")
            
            content = (resp.content or "").strip()
            try:
                parsed = json.loads(content)
            except Exception:
                try:
                    json_str = content[content.index("{"):content.rindex("}") + 1]
                    parsed = json.loads(json_str)
                except Exception:
                    parsed = {k: [] for k in aggregated.keys()}

            for key in aggregated.keys():
                val = parsed.get(key, [])
                if isinstance(val, list):
                    aggregated[key].extend(val)

        def dedup(lst: List[str]) -> List[str]:
            seen = set()
            out = []
            for s in lst:
                s_clean = s.strip()
                if s_clean and s_clean not in seen:
                    seen.add(s_clean)
                    out.append(s_clean)
            return out

        for k in aggregated:
            aggregated[k] = dedup(aggregated[k])

        vague_term_remediation = await self._generate_vague_term_remediation(aggregated["vague_terms"], text)

        return {
            'vague_terms': aggregated["vague_terms"],
            'vague_term_remediation': vague_term_remediation,
            'unclear_statements': aggregated["unclear_statements"],
            'missing_details': aggregated["missing_details"],
            'inconsistencies': aggregated["inconsistencies"],
            'grammar_issues': aggregated["grammar_issues"],
            'redundancies': aggregated["redundancies"],
            'total_issues': sum(len(v) if isinstance(v, list) else 0 for k, v in aggregated.items() if k != 'vague_term_remediation')
        }

    async def _generate_vague_term_remediation(self, vague_terms: List[str], document_text: str) -> List[Dict[str, str]]:
        """WITH TOKEN TRACKING"""
        if not vague_terms:
            return []
        
        print(f"💡 Generating remediation for {len(vague_terms)} vague terms...")
        
        remediation_list = []
        batch_size = 5
        for i in range(0, len(vague_terms), batch_size):
            batch = vague_terms[i:i+batch_size]
            
            prompt = f"""
            For each vague term, provide clear remediation:
            
            Vague terms:
            {json.dumps(batch, indent=2)}

            Context:
            {document_text[:1000]}

            Return JSON:
            [
              {{
                "vague_term": "<original>",
                "why_vague": "<explanation>",
                "suggested_replacement": "<specific alternative>",
                "example": "<usage example>",
                "severity": "<High/Medium/Low>"
              }}
            ]
            """
            
            try:
                resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
                
                # NEW: Track tokens
                self.token_tracker.track_api_call("vague_term_remediation", resp, "gpt-4o-mini")
                
                content = (resp.content or "").strip()
                
                try:
                    remediations = json.loads(content)
                except:
                    json_match = re.search(r'\[[\s\S]*\]', content)
                    if json_match:
                        remediations = json.loads(json_match.group())
                    else:
                        remediations = []
                
                if isinstance(remediations, list):
                    remediation_list.extend(remediations)
                    
            except Exception as e:
                print(f"⚠️ Error generating remediation: {e}")
                for term in batch:
                    remediation_list.append({
                        "vague_term": term,
                        "why_vague": "This term is unclear",
                        "suggested_replacement": "Replace with specific language",
                        "example": f"Instead of '{term}', specify exact meaning",
                        "severity": "Medium"
                    })
        
        return remediation_list

    def _calculate_content_quality_score(self, quality_scores: Dict, quality_issues: Dict) -> Dict[str, Any]:
        scores = [
            quality_scores.get('clarity_score', 5),
            quality_scores.get('completeness_score', 5),
            quality_scores.get('accuracy_score', 5),
            quality_scores.get('consistency_score', 5),
            quality_scores.get('readability_score', 5),
            quality_scores.get('organization_score', 5)
        ]
        
        average_score = round(sum(scores) / len(scores), 1)
        total_issues = quality_issues.get('total_issues', 0)
        penalty = min(2.0, total_issues * 0.1)
        final_score = max(0, round(average_score - penalty, 1))
        
        if final_score >= 8.5:
            rating = "Excellent"
            color = "success"
        elif final_score >= 7.0:
            rating = "Good"
            color = "info"
        elif final_score >= 5.5:
            rating = "Fair"
            color = "warning"
        else:
            rating = "Needs Improvement"
            color = "error"
        
        return {
            'overall_score': final_score,
            'average_dimension_score': average_score,
            'issue_penalty': penalty,
            'total_issues_found': total_issues,
            'quality_rating': rating,
            'rating_color': color,
            'dimension_scores': scores
        }

    # ----------------------
    # AGENT 4A: Content Improvement with token tracking
    # ----------------------

    async def _content_improvement_agent(self, state: WorkflowState) -> WorkflowState:
        print("✨ Content Improvement Agent...")
        cleaned_text = state['cleaned_content']['cleaned_text']
        analysis = state['automation_analysis']
        quality_scores = analysis.get('quality_scores', {})

        improved_document = await self._generate_improved_content_for_quality(cleaned_text, quality_scores)

        state['improved_document'] = improved_document
        state['current_step'] = 'content_improvement_complete'
        return state

    async def _generate_improved_content_for_quality(self, original_text: str, quality_scores: Dict) -> Dict[str, Any]:
        """WITH TOKEN TRACKING"""
        chunks = chunk_text_by_paragraphs(original_text, max_chunk_size=3500, overlap_paragraphs=1)
        improved_chunks = []
        all_improvements = []
        
        print(f"✨ Improving content quality...")
        
        for i, chunk in enumerate(chunks):
            prompt = f"""
            Improve this document section for overall content quality.

            Current scores:
            - Clarity: {quality_scores.get('clarity_score', 5)}/10
            - Completeness: {quality_scores.get('completeness_score', 5)}/10
            - Readability: {quality_scores.get('readability_score', 5)}/10

            Focus on clearer language, missing details, better flow.
            **Keep [IMAGE_X_ANALYSIS] blocks intact.**

            Return JSON:
            {{
              "improved_content": "<improved content>",
              "improvements_made": ["<improvement1>", "<improvement2>"]
            }}

            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            # NEW: Track tokens
            self.token_tracker.track_api_call("content_improvement", resp, "gpt-4o-mini")
            
            try:
                result = json.loads(resp.content)
                improved_chunks.append(result.get('improved_content', chunk))
                all_improvements.extend(result.get('improvements_made', []))
            except:
                improved_chunks.append(chunk)
        
        improved_content = "\n\n".join(improved_chunks)
        score_increase = min(2.5, (10 - quality_scores.get('clarity_score', 5)) * 0.4)
        
        return {
            "improved_content": improved_content,
            "improvements_made": list(set(all_improvements))[:15],
            "quality_score_increase": round(score_increase, 1),
            "new_clarity_score": min(10, quality_scores.get('clarity_score', 5) + score_increase * 0.5),
            "new_completeness_score": min(10, quality_scores.get('completeness_score', 5) + score_increase * 0.4),
            "new_readability_score": min(10, quality_scores.get('readability_score', 5) + score_increase * 0.5),
            "new_organization_score": min(10, quality_scores.get('organization_score', 5) + score_increase * 0.3)
        }

    # ----------------------
    # AUTOMATION AGENTS (with token tracking - abbreviated for space)
    # Note: Add token tracking to ALL automation agents using the same pattern
    # ----------------------

    async def _enhanced_automation_analysis_agent(self, state: WorkflowState) -> WorkflowState:
        print("🤖 Automation Analyzer...")
        cleaned_text = state['cleaned_content']['cleaned_text']

        rule_data = await self._extract_rule_data(cleaned_text)
        scoring_analysis = await self._perform_five_metric_analysis_on_full_content(cleaned_text, rule_data)
        improved_document = await self._generate_improved_actual_document(cleaned_text, scoring_analysis)

        comprehensive = {
            **scoring_analysis,
            'rule_data': rule_data,
            'overall_automation_score': self._calculate_overall_score(scoring_analysis),
            'improvement_recommendations': scoring_analysis.get('improvement_recommendations', []),
            'workflow_mode': 'full_automation'
        }

        state['automation_analysis'] = comprehensive
        state['improved_document'] = improved_document
        state['current_step'] = 'enhanced_analysis_complete'
        return state

    # Add token tracking to remaining automation agents similarly...
    # (For brevity, I'm showing the pattern - apply to all LLM calls)

    async def _perform_five_metric_analysis_on_full_content(self, text: str, rule_data: Dict) -> Dict[str, Any]:
        """WITH TOKEN TRACKING - Apply same pattern"""
        chunks = chunk_text_by_paragraphs(text, max_chunk_size=3500, overlap_paragraphs=1)
        chunk_scores = []
        
        for idx, chunk in enumerate(chunks):
            # ... existing prompt ...
            resp = await self.llm.ainvoke([HumanMessage(content=analysis_prompt)])
            
            # NEW: Track tokens
            self.token_tracker.track_api_call("automation_metric_analysis", resp, "gpt-4o-mini")
            
            # ... rest of processing ...
        
        # ... rest of method unchanged ...
        return {}  # Return scores as before

    # ----------------------
    # PUBLIC ENTRYPOINTS with token tracking
    # ----------------------

    async def process_document(self, pdf_path: str, workflow_mode: str = 'full_automation') -> Dict[str, Any]:
        """Process PDF with token tracking"""
        
        # NEW: Start token tracking
        document_name = Path(pdf_path).name
        
        try:
            doc = fitz.open(pdf_path)
            document_pages = len(doc)
            doc.close()
            
            with open(pdf_path, 'rb') as f:
                document_size = len(f.read())
            
            # Count images
            doc = fitz.open(pdf_path)
            total_images = sum(len(page.get_images()) for page in doc)
            doc.close()
            
        except Exception as e:
            print(f"⚠️ Error getting document metadata: {e}")
            document_pages = 0
            document_size = 0
            total_images = 0
        
        self.token_tracker.start_session(
            document_name=document_name,
            workflow_mode=workflow_mode,
            document_size=document_size,
            document_pages=document_pages,
            total_images=total_images
        )
        
        try:
            initial_state = WorkflowState(
                pdf_path=pdf_path,
                parsed_content={},
                cleaned_content={},
                automation_analysis={},
                improved_document={},
                similarity_matches={},
                automation_commands={},
                generated_script={},
                messages=[],
                current_step="starting",
                workflow_mode=workflow_mode
            )
            
            if workflow_mode == 'content_improvement':
                final_state = await self.content_workflow.ainvoke(initial_state)
            else:
                final_state = await self.full_workflow.ainvoke(initial_state)
            
            # NEW: End session successfully
            session_id = self.token_tracker.end_session(status="completed")
            
            return {
                'parsed_content': final_state['parsed_content'],
                'cleaned_content': final_state['cleaned_content'],
                'automation_analysis': final_state['automation_analysis'],
                'improved_document': final_state['improved_document'],
                'similarity_matches': final_state.get('similarity_matches', {}),
                'automation_commands': final_state.get('automation_commands', {}),
                'generated_script': final_state['generated_script'],
                'workflow_mode': workflow_mode,
                'token_usage': {  # NEW
                    'session_id': session_id,
                    'total_tokens': self.token_tracker.current_session_tokens['total_tokens'],
                    'prompt_tokens': self.token_tracker.current_session_tokens['prompt_tokens'],
                    'completion_tokens': self.token_tracker.current_session_tokens['completion_tokens'],
                    'agent_breakdown': self.token_tracker.agent_tokens.copy()
                }
            }
            
        except Exception as e:
            # NEW: Track failed session
            self.token_tracker.end_session(status="failed", error_message=str(e))
            raise e

    async def process_text_document(self, text_file_path: str, workflow_mode: str = 'full_automation') -> Dict[str, Any]:
        """Process text with token tracking"""
        with open(text_file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        
        # NEW: Start tracking
        document_name = Path(text_file_path).name
        self.token_tracker.start_session(
            document_name=document_name,
            workflow_mode=workflow_mode,
            document_size=len(text_content),
            document_pages=1,
            total_images=0
        )
        
        try:
            initial_state = WorkflowState(
                pdf_path=text_file_path,
                parsed_content={
                    'combined_text': text_content,
                    'page_breakdown': [],
                    'total_pages': 1,
                    'processing_summary': {
                        'total_text_length': len(text_content),
                        'pages_with_images': 0,
                        'total_images': 0,
                        'pages_with_multimodal_content': 0,
                        'image_analysis_count': 0,
                        'input_type': 'text'
                    },
                    'image_analysis': []
                },
                cleaned_content={},
                automation_analysis={},
                improved_document={},
                similarity_matches={},
                automation_commands={},
                generated_script={},
                messages=[],
                current_step="text_parsing_complete",
                workflow_mode=workflow_mode
            )

            initial_state = await self._text_cleaning_agent(initial_state)
            
            if workflow_mode == 'content_improvement':
                initial_state = await self._content_quality_scoring_agent(initial_state)
                initial_state = await self._content_improvement_agent(initial_state)
            else:
                initial_state = await self._enhanced_automation_analysis_agent(initial_state)
                # Add other automation agents...

            # NEW: End session
            session_id = self.token_tracker.end_session(status="completed")

            return {
                'parsed_content': initial_state['parsed_content'],
                'cleaned_content': initial_state['cleaned_content'],
                'automation_analysis': initial_state['automation_analysis'],
                'improved_document': initial_state['improved_document'],
                'similarity_matches': initial_state.get('similarity_matches', {}),
                'automation_commands': initial_state.get('automation_commands', {}),
                'generated_script': initial_state['generated_script'],
                'workflow_mode': workflow_mode,
                'token_usage': {  # NEW
                    'session_id': session_id,
                    'total_tokens': self.token_tracker.current_session_tokens['total_tokens'],
                    'prompt_tokens': self.token_tracker.current_session_tokens['prompt_tokens'],
                    'completion_tokens': self.token_tracker.current_session_tokens['completion_tokens'],
                    'agent_breakdown': self.token_tracker.agent_tokens.copy()
                }
            }
            
        except Exception as e:
            self.token_tracker.end_session(status="failed", error_message=str(e))
            raise e




    # ----------------------
    # Automation feature extraction (unchanged except tracking already added earlier)
    # ----------------------

    async def _ai_runbook_feature_extraction(self, text: str) -> Dict[str, Any]:
        chunks = chunk_text_by_paragraphs(text, max_chunk_size=4000, overlap_paragraphs=1)
        aggregated = {
            "commands": [],
            "vague_terms": [],
            "manual_decisions": [],
            "ui_interactions": [],
            "decision_points": []
        }

        print(f"🔍 Extracting features from document...")

        for idx, chunk in enumerate(chunks):
            prompt = f"""
            Analyze this automation/runbook document section and extract:

            - "commands": shell/CLI/API/SQL/script commands.
            - "vague_terms": unclear/non-testable phrases.
            - "manual_decisions": human judgment or approvals.
            - "ui_interactions": GUI/dashboard/web UI actions.
            - "decision_points": if/when/unless/depending on logic.

            Return JSON ONLY:

            {{
              "commands": ["..."],
              "vague_terms": ["..."],
              "manual_decisions": ["..."],
              "ui_interactions": ["..."],
              "decision_points": ["..."]
            }}

            DOCUMENT SECTION:
            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            # Token tracking
            self.token_tracker.track_api_call("runbook_feature_extraction", resp, "gpt-4o-mini")

            content = (resp.content or "").strip()
            try:
                parsed = json.loads(content)
            except Exception:
                try:
                    json_str = content[content.index("{"):content.rindex("}") + 1]
                    parsed = json.loads(json_str)
                except Exception:
                    parsed = {
                        "commands": [],
                        "vague_terms": [],
                        "manual_decisions": [],
                        "ui_interactions": [],
                        "decision_points": []
                    }

            for key in aggregated.keys():
                val = parsed.get(key, [])
                if isinstance(val, list):
                    aggregated[key].extend(val)

        def dedup(lst: List[str]) -> List[str]:
            seen = set()
            out = []
            for s in lst:
                s_clean = s.strip()
                if s_clean and s_clean not in seen:
                    seen.add(s_clean)
                    out.append(s_clean)
            return out

        for k in aggregated:
            aggregated[k] = dedup(aggregated[k])
        return aggregated

    async def _extract_rule_data(self, text: str) -> Dict[str, Any]:
        features = await self._ai_runbook_feature_extraction(text)

        commands = features.get("commands", [])
        vague_terms = features.get("vague_terms", [])
        manual_decisions = features.get("manual_decisions", [])
        ui_interactions = features.get("ui_interactions", [])
        decision_points = features.get("decision_points", [])

        vague_term_remediation = await self._generate_vague_term_remediation(vague_terms, text)

        return {
            'commands': {
                'total_commands': len(commands),
                'unique_commands': len(commands),
                'command_types': commands
            },
            'quality_flags': {
                'vague_terms': len(vague_terms),
                'manual_decisions': len(manual_decisions),
                'ui_interactions': len(ui_interactions),
                'vague_terms_list': vague_terms,
                'vague_term_remediation': vague_term_remediation,
                'manual_decisions_list': manual_decisions,
                'ui_interactions_list': ui_interactions
            },
            'logic_structure': {
                'decision_points': len(decision_points),
                'conditional_statements': len(decision_points),
                'decision_list': decision_points
            }
        }

    # ----------------------
    # 5‑metric automation analysis (with token tracking already partially shown)
    # ----------------------

    async def _perform_five_metric_analysis_on_full_content(self, text: str, rule_data: Dict) -> Dict[str, Any]:
        chunks = chunk_text_by_paragraphs(text, max_chunk_size=3500, overlap_paragraphs=1)
        chunk_scores = []
        
        print(f"📊 Analyzing document comprehensively for automation...")

        for idx, chunk in enumerate(chunks):
            chunk_length = len(chunk)
            analysis_prompt = f"""
            You are an expert runbook automation analyst. Score this document section (0–10) on:

            1. Clarity
            2. Determinism
            3. Logic/Decision structure
            4. Automation feasibility
            5. Observability

            Use natural reasoning focused on automation readiness.

            Return JSON:
            {{
                "clarity_score": <number>,
                "clarity_reasoning": "<text>",
                "determinism_score": <number>,
                "determinism_reasoning": "<text>",
                "logic_decision_score": <number>,
                "logic_decision_reasoning": "<text>",
                "automation_feasibility_score": <number>,
                "automation_feasibility_reasoning": "<text>",
                "observability_score": <number>,
                "observability_reasoning": "<text>",
                "chunk_weight": {chunk_length}
            }}

            DOCUMENT CONTENT:
            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=analysis_prompt)])
            self.token_tracker.track_api_call("automation_metric_analysis", resp, "gpt-4o-mini")

            try:
                chunk_analysis = json.loads(resp.content)
                chunk_analysis['chunk_weight'] = chunk_length
                chunk_scores.append(chunk_analysis)
            except Exception as e:
                print(f"⚠️ Error in automation analysis chunk: {e}")
                chunk_scores.append({
                    "clarity_score": 5,
                    "clarity_reasoning": "Error in analysis",
                    "determinism_score": 5,
                    "determinism_reasoning": "Error in analysis",
                    "logic_decision_score": 5,
                    "logic_decision_reasoning": "Error in analysis",
                    "automation_feasibility_score": 5,
                    "automation_feasibility_reasoning": "Error in analysis",
                    "observability_score": 5,
                    "observability_reasoning": "Error in analysis",
                    "chunk_weight": chunk_length
                })
        
        total_weight = sum(c['chunk_weight'] for c in chunk_scores)
        
        def weighted_avg(metric: str) -> float:
            return sum(c[metric] * c['chunk_weight'] for c in chunk_scores) / total_weight
        
        def synthesize_reasoning(metric: str) -> str:
            reasons = [c[metric] for c in chunk_scores if "Error" not in c[metric]]
            if not reasons:
                return "Analysis could not be completed."
            if len(reasons) == 1:
                return reasons[0]
            return " ".join(reasons)[:600]

        recommendations_prompt = f"""
        Based on automation scores:
        - Clarity: {weighted_avg('clarity_score'):.1f}
        - Determinism: {weighted_avg('determinism_score'):.1f}
        - Logic: {weighted_avg('logic_decision_score'):.1f}
        - Feasibility: {weighted_avg('automation_feasibility_score'):.1f}
        - Observability: {weighted_avg('observability_score'):.1f}

        Provide JSON:
        {{
            "improvement_recommendations": ["..."],
            "critical_issues": ["..."],
            "quick_wins": ["..."]
        }}
        """
        rec_resp = await self.llm.ainvoke([HumanMessage(content=recommendations_prompt)])
        self.token_tracker.track_api_call("automation_metric_recommendations", rec_resp, "gpt-4o-mini")

        try:
            recommendations = json.loads(rec_resp.content)
        except Exception:
            recommendations = {
                "improvement_recommendations": ["Improve clarity of steps", "Specify inputs/outputs better"],
                "critical_issues": ["Too many manual steps", "Missing error handling"],
                "quick_wins": ["Add logs", "Document API endpoints"]
            }

        return {
            "clarity_score": round(weighted_avg('clarity_score'), 1),
            "clarity_reasoning": synthesize_reasoning('clarity_reasoning'),
            "determinism_score": round(weighted_avg('determinism_score'), 1),
            "determinism_reasoning": synthesize_reasoning('determinism_reasoning'),
            "logic_decision_score": round(weighted_avg('logic_decision_score'), 1),
            "logic_decision_reasoning": synthesize_reasoning('logic_decision_reasoning'),
            "automation_feasibility_score": round(weighted_avg('automation_feasibility_score'), 1),
            "automation_feasibility_reasoning": synthesize_reasoning('automation_feasibility_reasoning'),
            "observability_score": round(weighted_avg('observability_score'), 1),
            "observability_reasoning": synthesize_reasoning('observability_reasoning'),
            "improvement_recommendations": recommendations.get('improvement_recommendations', []),
            "critical_issues": recommendations.get('critical_issues', []),
            "quick_wins": recommendations.get('quick_wins', []),
            "scoring_method": "comprehensive_document_automation_analysis"
        }

    # ----------------------
    # Improved automation document (with tracking)
    # ----------------------

    async def _generate_improved_actual_document(self, original_text: str, analysis: Dict) -> Dict[str, Any]:
        chunks = chunk_text_by_paragraphs(original_text, max_chunk_size=3500, overlap_paragraphs=1)
        improved_chunks = []
        all_improvements: List[str] = []
        
        print(f"✨ Improving document for automation readiness...")
        
        for i, chunk in enumerate(chunks):
            prompt = f"""
            Improve this runbook/automation document section to increase automation readiness.

            Current scores:
            - Clarity: {analysis.get('clarity_score', 5)}/10
            - Determinism: {analysis.get('determinism_score', 5)}/10
            - Feasibility: {analysis.get('automation_feasibility_score', 5)}/10

            Fix vague terms, implicit manual decisions, and missing observability.
            Keep [IMAGE_X_ANALYSIS] blocks unmodified.

            Return JSON:
            {{
              "improved_content": "<improved content>",
              "improvements_made": ["<improvement1>", "<improvement2>"]
            }}

            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            self.token_tracker.track_api_call("automation_document_improvement", resp, "gpt-4o-mini")

            try:
                result = json.loads(resp.content)
                improved_chunks.append(result.get('improved_content', chunk))
                all_improvements.extend(result.get('improvements_made', []))
            except Exception:
                improved_chunks.append(chunk)
        
        improved_content = "\n\n".join(improved_chunks)
        score_increase = min(2.0, (10 - analysis.get('automation_feasibility_score', 5)) * 0.3)
        
        return {
            "improved_content": improved_content,
            "improvements_made": list(set(all_improvements))[:10],
            "automation_score_increase": round(score_increase, 1),
            "new_clarity_score": min(10, analysis.get('clarity_score', 5) + score_increase * 0.4),
            "new_determinism_score": min(10, analysis.get('determinism_score', 5) + score_increase * 0.4),
            "new_automation_feasibility": min(10, analysis.get('automation_feasibility_score', 5) + score_increase)
        }

    # ----------------------
    # Similarity matching agent with token tracking
    # ----------------------

    async def _generate_document_summary(self, cleaned_text: str, analysis: Dict) -> str:
        """Summarize document for similarity search WITH TOKEN TRACKING"""
        chunks = chunk_text_by_paragraphs(cleaned_text, max_chunk_size=4000, overlap_paragraphs=1)
        partial_summaries: List[str] = []
        
        for idx, chunk in enumerate(chunks):
            prompt = f"""
            Summarize this automation/runbook document section for similarity search.

            Focus on:
            - Main purpose
            - Systems involved
            - Key steps and workflows
            - Important inputs/outputs

            Return 1–2 concise paragraphs.

            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            self.token_tracker.track_api_call("similarity_summary_generation", resp, "gpt-4o-mini")

            partial_summaries.append((resp.content or "").strip())
        
        return "\n\n".join(partial_summaries)

    def _generate_embedding(self, text: str) -> List[float]:
        try:
            resp = self.embedding_client.embeddings.create(
                input=text,
                model=self.azure_embedding_config['embedding_deployment']
            )
            return resp.data[0].embedding
        except Exception as e:
            print(f"Embedding error: {e}")
            return []

    def _find_similar_automations(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        if not query_embedding:
            return []
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            q = """
                SELECT
                  automation_name,
                  description,
                  steps,
                  1 - (embedding <=> %s::vector) AS similarity_score
                FROM automation_embeddings
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """
            cur.execute(q, (query_embedding, query_embedding, top_k))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            out = []
            for r in rows:
                score = float(r['similarity_score'])
                out.append({
                    'automation_name': r['automation_name'],
                    'description': r['description'],
                    'steps': r['steps'],
                    'similarity_score': score,
                    'similarity_percentage': round(score * 100, 2)
                })
            return out
        except Exception as e:
            print(f"Similarity error: {e}")
            return []

    async def _similarity_matching_agent(self, state: WorkflowState) -> WorkflowState:
        print("🔍 Similarity Matching Agent...")
        if not self.embedding_enabled:
            state['similarity_matches'] = {
                'document_summary': 'Embedding client not initialized',
                'similar_automations': [],
                'total_matches_found': 0,
                'error': 'embedding_disabled'
            }
            state['current_step'] = 'similarity_matching_skipped'
            return state

        cleaned_text = state['cleaned_content']['cleaned_text']
        analysis = state['automation_analysis']

        try:
            summary = await self._generate_document_summary(cleaned_text, analysis)
            emb = self._generate_embedding(summary)
            sims = self._find_similar_automations(emb, top_k=5)
            state['similarity_matches'] = {
                'document_summary': summary,
                'similar_automations': sims,
                'total_matches_found': len(sims)
            }
        except Exception as e:
            state['similarity_matches'] = {
                'document_summary': 'Error',
                'similar_automations': [],
                'total_matches_found': 0,
                'error': str(e)
            }

        state['current_step'] = 'similarity_matching_complete'
        return state

    # ----------------------
    # Automation commands agent with token tracking
    # ----------------------

    async def _automation_commands_agent(self, state: WorkflowState) -> WorkflowState:
        print("🤖 Automation Commands Agent...")
        improved_doc = state['improved_document']
        analysis = state['automation_analysis']
        improved_content = improved_doc.get('improved_content', state['cleaned_content']['cleaned_text'])

        automation_commands = await self._analyze_automation_commands(improved_content, analysis)
        state['automation_commands'] = automation_commands
        state['current_step'] = 'automation_commands_complete'
        return state

    async def _analyze_automation_commands(self, content: str, analysis: Dict) -> Dict[str, Any]:
        chunks = chunk_text_by_paragraphs(content, max_chunk_size=3500, overlap_paragraphs=1)
        all_automatable_steps = []
        all_ui_only_tasks = []
        
        print(f"🤖 Analyzing automation potential...")
        
        for i, chunk in enumerate(chunks):
            prompt = f"""
            Analyze this document section and identify:

            - automatable_steps: steps that can be implemented via scripts/APIs/CLI.
            - ui_only_tasks: steps that are only feasible via UI.

            Return JSON:
            {{
              "automatable_steps": [...],
              "ui_only_tasks": [...]
            }}

            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            self.token_tracker.track_api_call("automation_commands_analysis", resp, "gpt-4o-mini")

            try:
                result = json.loads(resp.content)
                all_automatable_steps.extend(result.get('automatable_steps', []))
                all_ui_only_tasks.extend(result.get('ui_only_tasks', []))
            except Exception:
                pass
        
        total_steps = len(all_automatable_steps) + len(all_ui_only_tasks)
        automation_pct = round((len(all_automatable_steps) / total_steps * 100), 2) if total_steps > 0 else 0
        
        return {
            "automatable_steps": all_automatable_steps,
            "ui_only_tasks": all_ui_only_tasks,
            "automation_summary": {
                "total_steps": total_steps,
                "automatable_steps": len(all_automatable_steps),
                "ui_only_steps": len(all_ui_only_tasks),
                "automation_percentage": automation_pct,
                "complexity_level": "High" if automation_pct < 40 else "Medium" if automation_pct < 70 else "Low"
            }
        }

    # ----------------------
    # Script generation agent with token tracking
    # ----------------------

    async def _script_generation_agent(self, state: WorkflowState) -> WorkflowState:
        print("📜 Script Generation Agent...")
        automation_commands = state['automation_commands']
        analysis = state['automation_analysis']

        automation_percentage = automation_commands.get('automation_summary', {}).get('automation_percentage', 0)
        if automation_percentage < 30:
            script_data = await self._generate_low_automation_explanation(automation_commands, automation_percentage)
        else:
            script_data = await self._generate_python_automation_script(automation_commands, analysis)

        state['generated_script'] = script_data
        state['current_step'] = 'complete'
        return state

    async def _generate_low_automation_explanation(self, automation_commands: Dict, percentage: float) -> Dict[str, Any]:
        ui_tasks = automation_commands.get('ui_only_tasks', [])
        explanation = f"# Automation Script Generation - Insufficient Automation Level\n\n"
        explanation += f"- Automation Percentage: {percentage}%\n"
        explanation += "- Threshold Required: 30% minimum\n\n"
        explanation += "## Reasons for Low Automation Score:\n\n"
        for i, t in enumerate(ui_tasks[:10], 1):
            task_desc = t if isinstance(t, str) else t.get('step_description', 'UI Task')
            explanation += f"{i}. {task_desc}\n"
        return {
            'script_type': 'Analysis Report',
            'automation_viable': False,
            'automation_percentage': percentage,
            'explanation': explanation,
            'recommendations': [
                'Add more technical details',
                'Replace UI steps with APIs/CLI',
                'Break down manual processes'
            ],
            'threshold_met': False,
            'code': None,
            'requirements': None,
            'execution_steps': None,
            'parameters_required': [],
            'script_description': 'Automation coverage below threshold',
            'automation_coverage': f"{percentage}% estimated automatable steps",
            'manual_steps_remaining': ui_tasks,
            'notes': 'Increase machine-actionable details before generating a script'
        }

    async def _generate_python_automation_script(self, automation_commands: Dict, analysis: Dict) -> Dict[str, Any]:
        prompt = f"""
        Generate a complete Python automation script based on this automation commands analysis.

        Return JSON:
        {{
          "code": "<python script>",
          "requirements": ["..."],
          "execution_steps": ["..."],
          "parameters_required": ["..."],
          "script_description": "<...>",
          "automation_coverage": "<...>",
          "manual_steps_remaining": ["..."],
          "notes": "<...>"
        }}

        AUTOMATION COMMANDS:
        {json.dumps(automation_commands, indent=2)}

        OVERALL AUTOMATION SCORE: {analysis.get('overall_automation_score', 6)}/10
        """
        resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
        self.token_tracker.track_api_call("python_script_generation", resp, "gpt-4o-mini")

        try:
            data = json.loads(resp.content)
        except Exception:
            data = {
                "code": "# Error generating script",
                "requirements": [],
                "execution_steps": [],
                "parameters_required": [],
                "script_description": "Error in generation",
                "automation_coverage": "Unknown",
                "manual_steps_remaining": [],
                "notes": "Failed to generate script"
            }
        
        data.update({
            'script_type': 'Python Automation Script',
            'automation_viable': True,
            'automation_percentage': automation_commands.get('automation_summary', {}).get('automation_percentage', 70),
            'threshold_met': True,
            'explanation': None
        })
        return data



