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

# ----------------------
# Utility: simple char-based chunking
# ----------------------

def chunk_text(text: str, chunk_size: int = 4000, overlap: int = 400) -> List[str]:
    """
    Chunk large text into overlapping pieces by characters.
    Ensures full coverage of the document with overlap for context.
    """
    text = text or ""
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(text[start:end])
        if end == n:
            break
        start = max(0, end - overlap)
        if start >= n:
            break
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

        self.workflow = self._build_workflow()

    # ----------------------
    # Workflow graph
    # ----------------------

    def _build_workflow(self) -> StateGraph:
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

    # ----------------------
    # AGENT 1: PDF parsing
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

                            image_block = f"\n[IMAGE_{img_index + 1}_ANALYSIS]:\n"
                            image_block += f"Description: {multimodal_result['description']}\n"
                            image_block += f"Purpose: {multimodal_result['purpose']}\n"
                            image_block += f"Automation Relevance: {multimodal_result['automation_relevance']}\n"
                            if multimodal_result['extracted_text'].strip():
                                image_block += f"Extracted Text: {multimodal_result['extracted_text']}\n"
                            else:
                                image_block += "Extracted Text: No text detected in image\n"
                            image_block += f"[END_IMAGE_{img_index + 1}_ANALYSIS]\n"

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
            if image_list:
                page_combined += f"\n--- IMAGES ANALYSIS FOR PAGE {page_num + 1} ---\n"
                page_combined += page_multimodal_content
                page_combined += f"--- END IMAGES ANALYSIS FOR PAGE {page_num + 1} ---\n"
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

    # ----------------------
    # AGENT 2: Cleaning (full doc via chunking)
    # ----------------------

    async def _text_cleaning_agent(self, state: WorkflowState) -> WorkflowState:
        print("🧹 Text Cleaning Agent...")
        raw_text = state['parsed_content']['combined_text']

        # basic structural cleanup (no truncation)
        cleaned_text_basic = self._basic_text_cleaning(raw_text)
        # AI filtering over ALL text via chunking
        filtered_text = await self._ai_content_filtering(cleaned_text_basic)
        # remove repeated headers/footers etc.
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
        chunks = chunk_text(text, chunk_size=4000, overlap=400)
        cleaned_chunks = []
        for i, chunk in enumerate(chunks):
            prompt = f"""
            You are cleaning a technical/automation document chunk.

            Tasks:
            - Remove headers, footers, boilerplate, page numbers and OCR noise.
            - Keep all process descriptions, steps, workflows, data definitions, business rules, commands, and image-analysis blocks.
            - Preserve order and technical detail. Do NOT summarize.

            Return ONLY the cleaned text for this chunk.

            CHUNK {i+1}/{len(chunks)}:
            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            cleaned_chunks.append((resp.content or "").strip())
        return "\n\n".join(cleaned_chunks).strip()

    def _remove_headers_footers(self, text: str) -> str:
        lines = text.split("\n")
        if len(lines) < 10:
            return text

        line_counts: Dict[str, int] = {}
        for line in lines:
            clean = re.sub(r'\d+', 'NUM', line.strip())
            if 5 < len(clean) < 80:
                line_counts[clean] = line_counts.get(clean, 0) + 1

        repetitive = {ln for ln, c in line_counts.items() if c >= 3}
        filtered = []
        for line in lines:
            clean = re.sub(r'\d+', 'NUM', line.strip())
            if clean not in repetitive:
                filtered.append(line)
        return "\n".join(filtered)

    # ----------------------
    # AI extraction of sections and key phrases (full doc via chunking)
    # ----------------------

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
        chunks = chunk_text(text, chunk_size=3000, overlap=300)
        phrases: List[str] = []

        for i, chunk in enumerate(chunks):
            prompt = f"""
            From this automation/runbook CHUNK, extract 5–10 key phrases that are
            most important for automation (technical terms, process names, tools,
            commands, systems, workflows, automation concepts).

            Return ONLY a comma-separated list of phrases.

            CHUNK {i+1}/{len(chunks)}:
            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
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
    # AI-based feature extraction (no regex)
    # ----------------------

    async def _ai_runbook_feature_extraction(self, text: str) -> Dict[str, Any]:
        chunks = chunk_text(text, chunk_size=4000, overlap=400)
        aggregated = {
            "commands": [],
            "vague_terms": [],
            "manual_decisions": [],
            "ui_interactions": [],
            "decision_points": []
        }

        for idx, chunk in enumerate(chunks):
            prompt = f"""
            Analyze this automation/runbook CHUNK and extract the following items using
            exact phrases from the text:

            - "commands": shell/CLI/API/SQL/script commands or imperative instructions.
            - "vague_terms": unclear/non-testable phrases (like "verify system is ok", "make sure it's fine").
            - "manual_decisions": phrases indicating human judgment/approval/review/decision.
            - "ui_interactions": phrases describing GUI/dashboard/web UI actions.
            - "decision_points": conditional/branching phrases (if/when/unless/depending on, etc.).

            Return JSON ONLY with this exact structure:

            {{
              "commands": ["..."],
              "vague_terms": ["..."],
              "manual_decisions": ["..."],
              "ui_interactions": ["..."],
              "decision_points": ["..."]
            }}

            Do NOT summarize or explain, just lists of exact phrases from this chunk.

            CHUNK {idx+1}/{len(chunks)}:
            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
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
    # AGENT 3: 5‑metric analysis (on FULL CLEANED TEXT)
    # ----------------------

    async def _enhanced_automation_analysis_agent(self, state: WorkflowState) -> WorkflowState:
        print("🤖 Automation Analyzer...")
        cleaned_text = state['cleaned_content']['cleaned_text']

        rule_data = await self._extract_rule_data(cleaned_text)
        scoring_analysis = await self._perform_five_metric_analysis(cleaned_text, rule_data)
        improved_document = await self._generate_improved_actual_document(cleaned_text, scoring_analysis)

        comprehensive = {
            **scoring_analysis,
            'rule_data': rule_data,
            'overall_automation_score': self._calculate_overall_score(scoring_analysis),
            'improvement_recommendations': scoring_analysis.get('improvement_recommendations', [])
        }

        state['automation_analysis'] = comprehensive
        state['improved_document'] = improved_document
        state['current_step'] = 'enhanced_analysis_complete'
        return state

    async def _perform_five_metric_analysis(self, text: str, rule_data: Dict) -> Dict[str, Any]:
        """
        Score on 5 metrics using the FULL cleaned document via chunking.
        The model sees the entire cleaned doc, chunk by chunk.
        """

        chunks = chunk_text(text, chunk_size=3500, overlap=400)
        # we give scoring context + a separate scoring instruction
        # but we keep the scoring JSON in one final call.
        # To respect context, we first condense all chunks into a "scoring view"
        # but *still derived from the whole cleaned text*.

        # Build a rich "scoring view" by concatenating LLM-normalized chunks
        scoring_view_parts: List[str] = []
        for idx, chunk in enumerate(chunks):
            prompt = f"""
            Normalize this runbook/automation CHUNK into a dense representation
            that preserves all details relevant to:
            - clarity of steps
            - determinism (input -> output)
            - logic/decision structure
            - automation feasibility
            - observability and logging

            Do NOT summarize away important details. Rephrase only to remove redundancy,
            keep all conditions, steps, and key signals.

            Return 1–3 short paragraphs.

            CHUNK {idx+1}/{len(chunks)}:
            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            scoring_view_parts.append((resp.content or "").strip())

        scoring_view = "\n\n".join(scoring_view_parts)

        analysis_prompt = f"""
        You are an expert runbook automation analyst. Using the following
        normalized representation of the FULL cleaned document, and the rule-data
        extracted by another agent, score the runbook on 5 metrics (0–10).

        RULE DATA:
        - Total Commands Found: {rule_data['commands']['total_commands']}
        - Vague Terms Found: {rule_data['quality_flags']['vague_terms']}
        - Manual Decision Points: {rule_data['quality_flags']['manual_decisions']}
        - UI Interactions: {rule_data['quality_flags']['ui_interactions']}
        - Decision Points: {rule_data['logic_structure']['decision_points']}

        Return your analysis as a JSON object with this exact structure:
        {{
            "clarity_score": <number 0-10>,
            "clarity_reasoning": "<explanation>",
            "determinism_score": <number 0-10>,
            "determinism_reasoning": "<explanation>",
            "logic_decision_score": <number 0-10>,
            "logic_decision_reasoning": "<explanation>",
            "automation_feasibility_score": <number 0-10>,
            "automation_feasibility_reasoning": "<explanation>",
            "observability_score": <number 0-10>,
            "observability_reasoning": "<explanation>",
            "improvement_recommendations": ["<rec1>", "<rec2>", "<rec3>"],
            "critical_issues": ["<issue1>", "<issue2>"],
            "quick_wins": ["<win1>", "<win2>"]
        }}

        FULL CLEANED DOCUMENT (normalized for scoring, but derived from all chunks):
        {scoring_view}
        """
        resp = await self.llm.ainvoke([HumanMessage(content=analysis_prompt)])
        return json.loads(resp.content)

    async def _generate_improved_actual_document(self, original_text: str, analysis: Dict) -> Dict[str, Any]:
        prompt = f"""
        Improve this automation/runbook document to increase automation readiness.

        Use these analysis scores:
        - Clarity: {analysis.get('clarity_score', 5)}/10
        - Determinism: {analysis.get('determinism_score', 5)}/10
        - Feasibility: {analysis.get('automation_feasibility_score', 5)}/10

        Fix vague terms, manual decisions where possible, and missing observability.

        Return JSON:
        {{
          "improved_content": "<full improved document>",
          "improvements_made": ["<improvement1>", "<improvement2>"],
          "automation_score_increase": <number>,
          "new_clarity_score": <number>,
          "new_determinism_score": <number>,
          "new_automation_feasibility": <number>
        }}

        ORIGINAL CLEANED DOCUMENT:
        {original_text}
        """
        resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
        return json.loads(resp.content)

    def _calculate_overall_score(self, analysis: Dict) -> float:
        scores = [
            analysis.get('clarity_score', 5),
            analysis.get('determinism_score', 5),
            analysis.get('logic_decision_score', 5),
            analysis.get('automation_feasibility_score', 5),
            analysis.get('observability_score', 5)
        ]
        return round(sum(scores) / len(scores), 1)

    # ----------------------
    # AGENT 4: Similarity matching (unchanged, but uses full doc summary)
    # ----------------------

    async def _generate_document_summary(self, cleaned_text: str, analysis: Dict) -> str:
        chunks = chunk_text(cleaned_text, chunk_size=4000, overlap=400)
        partial_summaries: List[str] = []
        for idx, chunk in enumerate(chunks):
            prompt = f"""
            Summarize this automation/runbook CHUNK for similarity search.
            Preserve purpose, systems, key steps and outcomes.
            Return 1–2 paragraphs.

            CHUNK {idx+1}/{len(chunks)}:
            {chunk}
            """
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            partial_summaries.append((resp.content or "").strip())
        summary = "\n\n".join(partial_summaries)
        return summary

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
    # AGENT 5: Automation commands (unchanged logic)
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
        prompt = f"""
        Analyze the improved document content and suggest specific automation commands for each step.

        Return JSON:
        {{
          "automatable_steps": [...],
          "ui_only_tasks": [...],
          "automation_summary": {{
             "total_steps": ...,
             "automatable_steps": ...,
             "ui_only_steps": ...,
             "automation_percentage": ...,
             "complexity_level": "High/Medium/Low"
          }}
        }}

        OVERALL AUTOMATION SCORE: {analysis.get('overall_automation_score', 6)}/10

        IMPROVED DOCUMENT:
        {content}
        """
        resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
        return json.loads(resp.content)

    # ----------------------
    # AGENT 6: Script generation (unchanged logic)
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

    async def _generate_low_automation_explanation(self, automation_commands: Dict, percentage: int) -> Dict[str, Any]:
        ui_tasks = automation_commands.get('ui_only_tasks', [])
        explanation = f"# Automation Script Generation - Insufficient Automation Level\n\n"
        explanation += f"- Automation Percentage: {percentage}%\n"
        explanation += "- Threshold Required: 30% minimum\n\n"
        explanation += "## Reasons for Low Automation Score:\n\n"
        for i, t in enumerate(ui_tasks, 1):
            explanation += f"{i}. {t.get('step_description', 'UI Task')}\n"
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
            'execution_steps': None
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
        data = json.loads(resp.content)
        data.update({
            'script_type': 'Python Automation Script',
            'automation_viable': True,
            'automation_percentage': automation_commands.get('automation_summary', {}).get('automation_percentage', 70),
            'threshold_met': True,
            'explanation': None
        })
        return data

    # ----------------------
    # Public entrypoints
    # ----------------------

    async def process_text_document(self, text_file_path: str) -> Dict[str, Any]:
        with open(text_file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()

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
            current_step="text_parsing_complete"
        )

        initial_state = await self._text_cleaning_agent(initial_state)
        initial_state = await self._enhanced_automation_analysis_agent(initial_state)
        initial_state = await self._similarity_matching_agent(initial_state)
        initial_state = await self._automation_commands_agent(initial_state)
        final_state = await self._script_generation_agent(initial_state)

        return {
            'parsed_content': final_state['parsed_content'],
            'cleaned_content': final_state['cleaned_content'],
            'automation_analysis': final_state['automation_analysis'],
            'improved_document': final_state['improved_document'],
            'similarity_matches': final_state.get('similarity_matches', {}),
            'automation_commands': final_state.get('automation_commands', {}),
            'generated_script': final_state['generated_script']
        }

    async def process_document(self, pdf_path: str) -> Dict[str, Any]:
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
            current_step="starting"
        )
        final_state = await self.workflow.ainvoke(initial_state)
        return {
            'parsed_content': final_state['parsed_content'],
            'cleaned_content': final_state['cleaned_content'],
            'automation_analysis': final_state['automation_analysis'],
            'improved_document': final_state['improved_document'],
            'similarity_matches': final_state.get('similarity_matches', {}),
            'automation_commands': final_state.get('automation_commands', {}),
            'generated_script': final_state['generated_script']
        }
