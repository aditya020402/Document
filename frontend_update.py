import streamlit as st
import asyncio
import json
from pathlib import Path
import tempfile
from typing import Dict, Any
import pandas as pd
import sqlite3

from streamlit_pdf_viewer import pdf_viewer
from document_automation_workflow import DocumentAutomationWorkflow
from token_tracker import TokenTracker  # for simple aggregate stats display

st.set_page_config(
    page_title="Document Automation Analyzer",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Document Automation Analyzer")
st.markdown("Upload a document to analyze automation readiness or improve general content quality.")

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = None
if 'input_mode' not in st.session_state:
    st.session_state.input_mode = 'pdf'
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'workflow_mode' not in st.session_state:
    st.session_state.workflow_mode = 'full_automation'

# DB CONFIG FOR AUTOMATION SIMILARITY (unchanged)
DB_CONFIG = {
    'dbname': 'automation_db',
    'user': 'your_username',
    'password': 'your_password',
    'host': 'localhost',
    'port': '5432'
}

AZURE_EMBEDDING_CONFIG = {
    'api_key': 'your-azure-api-key',
    'api_version': '2023-05-15',
    'endpoint': 'https://your-resource.openai.azure.com/',
    'embedding_deployment': 'text-embedding-ada-002'
}

# ----------------------
# Workflow Mode Selector
# ----------------------

st.markdown("### 🎯 Select Analysis Mode")
col_mode_1, col_mode_2 = st.columns(2)

with col_mode_1:
    if st.button(
        "🤖 Full Automation Analysis", 
        use_container_width=True,
        type="primary" if st.session_state.workflow_mode == 'full_automation' else "secondary"
    ):
        st.session_state.workflow_mode = 'full_automation'

with col_mode_2:
    if st.button(
        "📝 Content Quality Improvement", 
        use_container_width=True,
        type="primary" if st.session_state.workflow_mode == 'content_improvement' else "secondary"
    ):
        st.session_state.workflow_mode = 'content_improvement'

if st.session_state.workflow_mode == 'full_automation':
    st.info(
        "**Full Automation Analysis**: parses, cleans, scores automation readiness, "
        "finds similar automations, and generates a Python script when feasible."
    )
else:
    st.success(
        "**Content Quality Improvement**: focuses purely on clarity, completeness, "
        "readability and consistency, plus vague term remediation and improved text."
    )

st.divider()

# ----------------------
# Input selection
# ----------------------

st.markdown("### Choose Input Method")
input_mode = st.radio(
    "Select how you want to provide your document:",
    options=['Upload PDF File', 'Paste/Type Text'],
    horizontal=True,
    help="Upload a PDF or paste raw text."
)

uploaded_file = None
text_input = None
tmp_file_path = None

if input_mode == 'Upload PDF File':
    st.markdown("### 📤 Upload PDF Document")
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf']
    )
    
    if uploaded_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name
        
        st.success(f"✅ File uploaded: **{uploaded_file.name}**")
        
        st.markdown("#### 📄 Document Preview")
        pdf_viewer(uploaded_file.getvalue(), width=700, height=400, annotations=[], render_text=True)

else:
    st.markdown("### 📝 Paste or Type Your Document")
    text_input = st.text_area(
        "Paste your document content here",
        height=400,
        placeholder="Paste your runbook, SOP, policy, or technical doc here...",
        help="At least 50 characters recommended."
    )
    
    if text_input and len(text_input.strip()) >= 50:
        word_count = len(text_input.split())
        char_count = len(text_input)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Characters", f"{char_count:,}")
        with c2:
            st.metric("Words", f"{word_count:,}")
        with c3:
            st.metric("Lines", len(text_input.split('\n')))
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_file:
            tmp_file.write(text_input)
            tmp_file_path = tmp_file.name
        
        st.success(f"✅ Text content ready for analysis ({word_count} words)")
        
        with st.expander("📄 Preview Pasted Content", expanded=False):
            st.text_area(
                "Content Preview",
                value=text_input[:1000] + "..." if len(text_input) > 1000 else text_input,
                height=200,
                disabled=True,
                label_visibility="collapsed"
            )
    elif text_input:
        st.warning("⚠️ Please paste at least 50 characters.")

# ----------------------
# Process Button
# ----------------------

if ((input_mode == 'Upload PDF File' and uploaded_file is not None) or 
    (input_mode == 'Paste/Type Text' and text_input and len(text_input.strip()) >= 50)):
    
    label = "🤖 Analyze for Automation" if st.session_state.workflow_mode == 'full_automation' else "📝 Analyze Content Quality"
    
    if st.button(label, type="primary", use_container_width=True):
        with st.spinner(f"🔄 Processing document in {st.session_state.workflow_mode.replace('_', ' ').title()} mode..."):
            try:
                workflow = DocumentAutomationWorkflow(
                    db_config=DB_CONFIG,
                    azure_embedding_config=AZURE_EMBEDDING_CONFIG
                )
                
                if input_mode == 'Upload PDF File':
                    results = asyncio.run(workflow.process_document(tmp_file_path, st.session_state.workflow_mode))
                else:
                    results = asyncio.run(workflow.process_text_document(tmp_file_path, st.session_state.workflow_mode))
                
                st.session_state.results = results
                st.session_state.processing = False
                st.success("✅ Analysis complete! See results below.")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error processing document: {str(e)}")
                st.exception(e)

# ----------------------
# Results + Token usage
# ----------------------

if st.session_state.results:
    results = st.session_state.results
    workflow_mode = results.get('workflow_mode', 'full_automation')

    # Top-level summary row: document + token usage
    st.divider()
    st.markdown("### 📋 Session Summary")

    col_a, col_b, col_c, col_d = st.columns(4)

    token_usage = results.get('token_usage', {})
    total_tokens = token_usage.get('total_tokens', 0)
    prompt_tokens = token_usage.get('prompt_tokens', 0)
    completion_tokens = token_usage.get('completion_tokens', 0)

    with col_a:
        st.metric("Total Tokens", f"{total_tokens:,}")
    with col_b:
        st.metric("Prompt Tokens", f"{prompt_tokens:,}")
    with col_c:
        st.metric("Completion Tokens", f"{completion_tokens:,}")
    with col_d:
        st.metric("Session ID", token_usage.get('session_id', "N/A"))

    # Agent breakdown (if available)
    if token_usage.get('agent_breakdown'):
        with st.expander("🔍 Token Usage by Agent", expanded=False):
            agent_rows = []
            for agent_name, data in token_usage['agent_breakdown'].items():
                agent_rows.append({
                    "Agent": agent_name,
                    "Prompt Tokens": data.get('prompt_tokens', 0),
                    "Completion Tokens": data.get('completion_tokens', 0),
                    "Total Tokens": data.get('total_tokens', 0),
                    "Calls": data.get('call_count', 0)
                })
            df_agents = pd.DataFrame(agent_rows).sort_values("Total Tokens", ascending=False)
            st.dataframe(df_agents, use_container_width=True)

    # Optional global stats from DB
    tracker = TokenTracker()  # re-uses same DB
    global_stats = tracker.get_total_usage()
    with st.expander("📈 Global Token Usage Summary (all documents)", expanded=False):
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            st.metric("Documents Processed", global_stats['total_documents'])
        with g2:
            st.metric("Total Tokens", f"{global_stats['total_tokens']:,}")
        with g3:
            st.metric("Avg Tokens / Document", f"{global_stats['avg_tokens_per_document']:,}")
        with g4:
            st.metric("Total Analysis Time (s)", global_stats['total_analysis_time_seconds'])

    # ------------------ Tabs layout ------------------

    if workflow_mode == 'content_improvement':
        tab1, tab2, tab3, tab4 = st.tabs([
            "📄 Raw Content",
            "🧹 Cleaned Content",
            "📊 Content Quality Analysis",
            "✨ Improved Document"
        ])
    else:
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📄 Raw Content",
            "🧹 Cleaned Content",
            "🤖 Automation Analysis",
            "🔍 Similar Automations",
            "✨ Improved Document",
            "📜 Script Generation"
        ])

    # TAB 1: Raw content
    with tab1:
        st.subheader("📄 Raw Extracted Content")
        if 'processing_summary' in results['parsed_content']:
            summary = results['parsed_content']['processing_summary']
            if input_mode == 'Upload PDF File':
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Total Pages", results['parsed_content'].get('total_pages', 0))
                with c2:
                    st.metric("Pages with Images", summary.get('pages_with_images', 0))
                with c3:
                    st.metric("Total Images", summary.get('total_images', 0))
                with c4:
                    st.metric("Raw Text Length", f"{summary.get('total_text_length', 0):,}")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Content Length", f"{summary.get('total_text_length', 0):,}")
                with c2:
                    st.metric("Input Type", "Text")

        st.text_area(
            "Raw Content",
            value=results['parsed_content']['combined_text'],
            height=400,
            disabled=True
        )

        if input_mode == 'Upload PDF File' and 'page_breakdown' in results['parsed_content']:
            st.markdown("#### 📊 Page Breakdown")
            st.dataframe(pd.DataFrame(results['parsed_content']['page_breakdown']), use_container_width=True)

        if input_mode == 'Upload PDF File' and results['parsed_content'].get('image_analysis'):
            st.markdown("#### 🖼️ Image Analysis")
            with st.expander("View image analyses", expanded=False):
                for i, img_analysis in enumerate(results['parsed_content']['image_analysis'], 1):
                    st.markdown(f"##### Image {i} - Page {img_analysis.get('page', 'Unknown')}")
                    st.markdown("**Extracted Text**")
                    txt = img_analysis.get('extracted_text', '')
                    st.code(txt if txt.strip() else "No text detected")
                    st.markdown("**Description**")
                    st.write(img_analysis.get('image_description', 'N/A'))
                    st.markdown("**Purpose**")
                    st.write(img_analysis.get('purpose', 'N/A'))
                    st.markdown("**Automation Relevance**")
                    st.write(img_analysis.get('automation_relevance', 'N/A'))
                    st.markdown("---")

    # TAB 2: Cleaned content
    with tab2:
        st.subheader("🧹 Cleaned & Processed Content")
        stats = results['cleaned_content'].get('cleaning_stats', {})
        if stats:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Original Length", f"{stats.get('original_length', 0):,}")
            with c2:
                st.metric("Cleaned Length", f"{stats.get('cleaned_length', 0):,}")
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
            st.markdown("#### Key Sections")
            sections = structured.get('sections', {})
            if sections.get('process_descriptions'):
                with st.expander("Process Descriptions", expanded=False):
                    for i, desc in enumerate(sections['process_descriptions'], 1):
                        st.markdown(f"**{i}.** {desc}")
            if sections.get('task_instructions'):
                with st.expander("Task Instructions", expanded=False):
                    for i, desc in enumerate(sections['task_instructions'], 1):
                        st.markdown(f"**{i}.** {desc}")
            if structured.get('key_phrases'):
                st.markdown("#### 🔑 Key Phrases")
                st.write(", ".join(structured['key_phrases']))

    # TAB 3: content OR automation analysis (already implemented in previous message)
    # Use the same Tab 3 code you already integrated earlier for:
    # - content_improvement -> content quality 6-metric dashboard
    # - full_automation -> automation 5-metric dashboard
    # (No token-specific UI changes needed there.)

    # TAB 4–6: same as previous version (similar automations, improved doc, script)
    # They don't need extra token UI; token info is already shown at top.
