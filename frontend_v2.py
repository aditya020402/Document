import streamlit as st
import asyncio
import tempfile
from pathlib import Path
import pandas as pd

from streamlit_pdf_viewer import pdf_viewer
from document_automation_workflow import DocumentAutomationWorkflow

st.set_page_config(page_title="Document Automation Analyzer", page_icon="📄", layout="wide")

st.title("📄 Document Automation Analyzer")
st.markdown("Upload a PDF or paste text to analyze automation readiness, vague terms, clarity suggestions, similarity, and scripts.")

if 'workflow_results' not in st.session_state:
    st.session_state.workflow_results = None

st.markdown("### 📥 Choose Input Method")
input_method = st.radio(
    "Select how you want to provide your document:",
    options=["Upload PDF File", "Paste/Type Text"],
    horizontal=True
)

uploaded_file = None
text_input = None
tmp_file_path = None

if input_method == "Upload PDF File":
    st.markdown("#### 📎 Upload PDF Document")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    if uploaded_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_file_path = tmp.name
        st.success(f"✅ File uploaded: {uploaded_file.name}")
        st.markdown("**Document Preview:**")
        pdf_viewer(uploaded_file.getvalue(), width=700, height=400, annotations=[], render_text=True)
else:
    st.markdown("#### ✍️ Paste or Type Your Document")
    text_input = st.text_area(
        "Paste your document content here:",
        height=400,
        placeholder="Paste your runbook, process document, or technical documentation here..."
    )
    if text_input and len(text_input.strip()) > 50:
        word_count = len(text_input.split())
        char_count = len(text_input)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Characters", f"{char_count:,}")
        with c2:
            st.metric("Words", f"{word_count:,}")
        with c3:
            st.metric("Lines", len(text_input.splitlines()))
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as tmp:
            tmp.write(text_input)
            tmp_file_path = tmp.name
        st.success(f"✅ Text content ready ({word_count} words)")
    elif text_input:
        st.warning("⚠️ Please paste at least 50 characters.")

ready = (input_method == "Upload PDF File" and uploaded_file is not None) or (
    input_method == "Paste/Type Text" and text_input and len(text_input.strip()) > 50
)

if ready:
    if st.button("🚀 Analyze Document for Automation", type="primary", use_container_width=True):
        with st.spinner("Processing document through AI agents (with paragraph-based chunking)..."):
            try:
                db_config = {
                    'dbname': 'automation_db',
                    'user': 'postgres',
                    'password': 'your_password',
                    'host': 'localhost',
                    'port': '5432'
                }
                azure_embedding_config = {
                    'api_key': 'your-azure-api-key',
                    'api_version': '2023-05-15',
                    'endpoint': 'https://your-resource.openai.azure.com/',
                    'embedding_deployment': 'text-embedding-ada-002'
                }
                workflow = DocumentAutomationWorkflow(
                    db_config=db_config,
                    azure_embedding_config=azure_embedding_config
                )
                if input_method == "Upload PDF File":
                    res = asyncio.run(workflow.process_document(tmp_file_path))
                else:
                    res = asyncio.run(workflow.process_text_document(tmp_file_path))
                st.session_state.workflow_results = res
                st.success("✅ Analysis complete. See results below.")
            except Exception as e:
                st.error(f"❌ Error processing document: {e}")
                st.exception(e)

results = st.session_state.workflow_results

if results:
    # NEW: 7 tabs instead of 6
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📄 Raw Content",
        "🧹 Cleaned Content",
        "🎯 Automation Analysis",
        "💡 Vague Term Remediation",  # NEW TAB
        "🔍 Similar Automations",
        "📈 Improved Document",
        "🤖 Script Generation"
    ])

    # ----------------------
    # Tab 1: Raw
    # ----------------------
    with tab1:
        st.subheader("Raw Extracted Content")
        summary = results['parsed_content'].get('processing_summary', {})
        if input_method == "Upload PDF File":
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Total Pages", results['parsed_content'].get('total_pages', 0))
            with c2:
                st.metric("Pages with Images", summary.get('pages_with_images', 0))
            with c3:
                st.metric("Total Images", summary.get('total_images', 0))
            with c4:
                st.metric("Raw Text Length", f"{summary.get('total_text_length', 0):,} chars")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Input Type", "Text")
            with c2:
                st.metric("Content Length", f"{summary.get('total_text_length', 0):,} chars")
            with c3:
                st.metric("Processing Method", "Direct Text")

        st.text_area(
            "Raw Content",
            value=results['parsed_content']['combined_text'],
            height=400,
            disabled=True
        )

        if input_method == "Upload PDF File" and results['parsed_content'].get('page_breakdown'):
            st.markdown("**Page Processing Details:**")
            dfp = pd.DataFrame(results['parsed_content']['page_breakdown'])
            st.dataframe(dfp, use_container_width=True)

    # ----------------------
    # Tab 2: Cleaned
    # ----------------------
    with tab2:
        st.subheader("Cleaned & Processed Content")
        stats = results['cleaned_content'].get('cleaning_stats', {})
        if stats:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Original Length", f"{stats.get('original_length', 0):,} chars")
            with c2:
                st.metric("Cleaned Length", f"{stats.get('cleaned_length', 0):,} chars")
            with c3:
                st.metric("Noise Removed", f"{stats.get('reduction_percentage', 0)}%")
            with c4:
                st.metric("Sections Found", stats.get('sections_identified', 0))

        st.text_area(
            "Cleaned Content",
            value=results['cleaned_content'].get('cleaned_text', ''),
            height=350,
            disabled=True
        )

        structured = results['cleaned_content'].get('structured_content', {})
        if structured:
            st.markdown("**🔍 Key Sections Identified:**")
            secs = structured.get('sections', {})
            if secs.get('process_descriptions'):
                st.markdown("**Process Descriptions:**")
                with st.expander("View all process descriptions", expanded=False):
                    for i, s in enumerate(secs['process_descriptions'], 1):
                        st.markdown(f"**{i}.** {s}")
            if secs.get('task_instructions'):
                st.markdown("**Task Instructions:**")
                with st.expander("View all task instructions", expanded=False):
                    for i, s in enumerate(secs['task_instructions'], 1):
                        st.markdown(f"**{i}.** {s}")

            key_phrases = structured.get('key_phrases', [])
            if key_phrases:
                st.markdown("**🔑 Key Automation Phrases:**")
                st.success(", ".join(f"`{p}`" for p in key_phrases))

    # ----------------------
    # Tab 3: Automation Analysis
    # ----------------------
    with tab3:
        st.subheader("🎯 Automation Analysis (5 Metrics)")
        analysis = results['automation_analysis']

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("Clarity", f"{analysis.get('clarity_score', 5)}/10")
        with c2:
            st.metric("Determinism", f"{analysis.get('determinism_score', 5)}/10")
        with c3:
            st.metric("Logic", f"{analysis.get('logic_decision_score', 5)}/10")
        with c4:
            st.metric("Feasibility", f"{analysis.get('automation_feasibility_score', 5)}/10")
        with c5:
            st.metric("Observability", f"{analysis.get('observability_score', 5)}/10")

        st.metric("Overall Automation Score", f"{analysis.get('overall_automation_score', 5.0)}/10")

        colA, colB = st.columns(2)
        with colA:
            st.markdown("#### Reasoning")
            st.markdown("**Clarity:**")
            st.write(analysis.get('clarity_reasoning', 'N/A'))
            st.markdown("**Determinism:**")
            st.write(analysis.get('determinism_reasoning', 'N/A'))
            st.markdown("**Logic / Decisions:**")
            st.write(analysis.get('logic_decision_reasoning', 'N/A'))
            st.markdown("**Feasibility:**")
            st.write(analysis.get('automation_feasibility_reasoning', 'N/A'))
            st.markdown("**Observability:**")
            st.write(analysis.get('observability_reasoning', 'N/A'))

        with colB:
            st.markdown("#### Quality Flags (LLM-detected)")
            rule_data = analysis.get('rule_data', {})
            qflags = rule_data.get('quality_flags', {})

            vague_list = qflags.get('vague_terms_list', [])
            manual_list = qflags.get('manual_decisions_list', [])
            ui_list = qflags.get('ui_interactions_list', [])

            st.markdown("**Vague Terms Detected:**")
            if vague_list:
                for i, v in enumerate(vague_list, 1):
                    st.markdown(f"{i}. {v}")
            else:
                st.info("No vague terms detected.")

            st.markdown("**Manual Decision Phrases:**")
            if manual_list:
                for i, v in enumerate(manual_list, 1):
                    st.markdown(f"{i}. {v}")
            else:
                st.info("No explicit manual decision phrases detected.")

            st.markdown("**UI Interaction Phrases:**")
            if ui_list:
                for i, v in enumerate(ui_list, 1):
                    st.markdown(f"{i}. {v}")
            else:
                st.info("No UI interaction phrases detected.")

            if analysis.get('improvement_recommendations'):
                st.markdown("#### Improvement Recommendations")
                for r in analysis['improvement_recommendations']:
                    st.success(f"- {r}")

    # ----------------------
    # Tab 4: NEW - Vague Term Remediation
    # ----------------------
    with tab4:
        st.subheader("💡 Vague Term Remediation Suggestions")
        
        vague_suggestions = results.get('vague_term_suggestions', {})
        
        if not vague_suggestions or vague_suggestions.get('total_vague_terms', 0) == 0:
            st.success("✅ No vague terms detected! Your document has excellent clarity for automation.")
        else:
            st.info(vague_suggestions.get('summary', ''))
            
            suggestions_list = vague_suggestions.get('suggestions', [])
            
            if suggestions_list:
                st.markdown(f"### Found {len(suggestions_list)} Vague Terms - Click Each for Remediation Strategies")
                
                for idx, suggestion in enumerate(suggestions_list, 1):
                    vague_term = suggestion.get('vague_term', 'Unknown')
                    issue_type = suggestion.get('issue_type', 'unknown')
                    
                    # Color code by issue type
                    if 'ambiguity' in issue_type.lower():
                        badge_color = "🔴"
                    elif 'underspecification' in issue_type.lower() or 'missing' in issue_type.lower():
                        badge_color = "🟠"
                    elif 'subjective' in issue_type.lower() or 'unclear' in issue_type.lower():
                        badge_color = "🟡"
                    else:
                        badge_color = "⚪"
                    
                    with st.expander(f"{badge_color} #{idx}: \"{vague_term}\" - {issue_type}", expanded=(idx == 1)):
                        st.markdown(f"**Original Vague Phrase:** `{vague_term}`")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("#### 🔍 Issue Analysis")
                            st.write(f"**Issue Type:** {issue_type}")
                            st.write(f"**Why Vague:** {suggestion.get('why_vague', 'N/A')}")
                            
                            st.markdown("#### 🎯 Automation Approach")
                            st.info(suggestion.get('automation_approach', 'N/A'))
                        
                        with col2:
                            st.markdown("#### ✅ Suggested Replacements")
                            replacements = suggestion.get('suggested_replacements', [])
                            if replacements:
                                for i, rep in enumerate(replacements, 1):
                                    st.success(f"**Option {i}:** {rep}")
                            else:
                                st.warning("No replacements suggested")
                            
                            st.markdown("#### ❓ Clarifying Questions to Ask")
                            questions = suggestion.get('clarifying_questions', [])
                            if questions:
                                for q in questions:
                                    st.markdown(f"- {q}")
                            else:
                                st.info("No clarifying questions needed")
                        
                        st.markdown("#### 📝 Example Improvement")
                        st.code(suggestion.get('example_improvement', 'N/A'), language='text')
                        
                        st.divider()

    # ----------------------
    # Tab 5: Similarity
    # ----------------------
    with tab5:
        st.subheader("🔍 Similar Existing Automations")
        sim = results.get('similarity_matches', {})
        if sim.get('error'):
            st.warning(f"Similarity matching unavailable: {sim['error']}")
        else:
            st.markdown("### Document Summary Used for Matching")
            st.info(sim.get('document_summary', 'N/A'))
            autos = sim.get('similar_automations', [])
            if autos:
                for i, a in enumerate(autos, 1):
                    pct = a.get('similarity_percentage', 0)
                    with st.expander(f"#{i} {a['automation_name']} ({pct}% similar)", expanded=(i == 1)):
                        st.markdown(f"**Similarity:** {pct}%")
                        st.markdown("**Description:**")
                        st.write(a['description'])
                        st.markdown("**Steps:**")
                        st.text_area("Steps", value=a['steps'], height=200, disabled=True, key=f"steps_{i}")
            else:
                st.info("No similar automations found.")

    # ----------------------
    # Tab 6: Improved document
    # ----------------------
    with tab6:
        st.subheader("📈 AI-Improved Document")
        imp = results.get('improved_document', {})
        if imp:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Score Increase", f"+{imp.get('automation_score_increase', 0)}")
            with c2:
                st.metric("New Clarity", f"{imp.get('new_clarity_score', 0)}/10")
            with c3:
                st.metric("New Feasibility", f"{imp.get('new_automation_feasibility', 0)}/10")

            if imp.get('improvements_made'):
                st.markdown("### Improvements Applied")
                for im in imp['improvements_made']:
                    st.success(f"- {im}")

            st.text_area(
                "Improved Document",
                value=imp.get('improved_content', ''),
                height=500,
                disabled=True
            )

    # ----------------------
    # Tab 7: Script generation
    # ----------------------
    with tab7:
        st.subheader("🤖 Automation Script Generation")
        script = results.get('generated_script', {})
        if not script:
            st.info("No script data.")
        elif not script.get('automation_viable', True):
            st.warning(f"Automation level too low ({script.get('automation_percentage', 0)}%) for script generation.")
            st.text_area(
                "Analysis",
                value=script.get('explanation', ''),
                height=400,
                disabled=True
            )
        else:
            st.success("Python automation script generated.")
            st.text_area(
                "Script",
                value=script.get('code', ''),
                height=500,
                disabled=True
            )
            if script.get('requirements'):
                st.markdown("**Requirements:**")
                st.code("\n".join(script['requirements']))
            if script.get('execution_steps'):
                st.markdown("**How to Run:**")
                for i, step in enumerate(script['execution_steps'], 1):
                    st.markdown(f"{i}. {step}")

# cleanup temp file
if tmp_file_path and Path(tmp_file_path).exists():
    Path(tmp_file_path).unlink(missing_ok=True)
