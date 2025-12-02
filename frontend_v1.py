import streamlit as st
import asyncio
import json
from pathlib import Path
import tempfile
from typing import Dict, Any
import pandas as pd

from streamlit_pdf_viewer import pdf_viewer
from document_automation_workflow import DocumentAutomationWorkflow

st.set_page_config(
    page_title="Document Automation Analyzer",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Document Automation Analyzer")
st.markdown("Upload a PDF document or paste text to get AI-powered automation recommendations and generated scripts")

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = None
if 'input_mode' not in st.session_state:
    st.session_state.input_mode = 'pdf'
if 'processing' not in st.session_state:
    st.session_state.processing = False

# Simple hardcoded config (as it was before)
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

# Input selection (simple radio as before)
input_mode = st.radio(
    "Choose input method:",
    options=['pdf', 'text'],
    format_func=lambda x: "📄 PDF Upload" if x == 'pdf' else "📝 Text Input",
    horizontal=True
)

if input_mode == 'pdf':
    st.subheader("📤 Upload PDF Document")
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload a PDF document to analyze for automation potential"
    )
    
    if uploaded_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.read())
            pdf_path = tmp_file.name
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.success(f"📄 Loaded: **{uploaded_file.name}**")
        with col2:
            if st.button("🚀 Analyze Document", type="primary", use_container_width=True):
                st.session_state.input_mode = 'pdf'
                st.session_state.processing = True
                st.session_state.pdf_path = pdf_path
                st.rerun()

elif input_mode == 'text':
    st.subheader("📝 Paste Text Content")
    text_input = st.text_area(
        "Paste your document text here",
        height=300,
        placeholder="Paste your automation/runbook document text here..."
    )
    
    if st.button("🚀 Analyze Text", type="primary"):
        if text_input.strip():
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_file:
                tmp_file.write(text_input)
                pdf_path = tmp_file.name
            
            st.session_state.input_mode = 'text'
            st.session_state.processing = True
            st.session_state.pdf_path = pdf_path
            st.rerun()

# Processing
if st.session_state.get('processing', False):
    try:
        workflow = DocumentAutomationWorkflow(
            db_config=DB_CONFIG,
            azure_embedding_config=AZURE_EMBEDDING_CONFIG
        )
        
        with st.spinner("🔄 Analyzing document..."):
            if st.session_state.input_mode == 'pdf':
                results = asyncio.run(workflow.process_document(st.session_state.pdf_path))
            else:
                results = asyncio.run(workflow.process_text_document(st.session_state.pdf_path))
        
        st.session_state.results = results
        st.session_state.processing = False
        st.success("✅ Analysis complete!")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.session_state.processing = False

# Results display
if st.session_state.get('results'):
    results = st.session_state.results
    
    tabs = st.tabs([
        "📊 Overview", 
        "📄 Parsed", 
        "🧹 Cleaned", 
        "🤖 Analysis", 
        "🔍 Similar", 
        "✨ Improved", 
        "📜 Script"
    ])
    
    # Tab 1: Overview
    with tabs[0]:
        st.header("📊 Analysis Overview")
        automation_analysis = results.get('automation_analysis', {})
        overall_score = automation_analysis.get('overall_automation_score', 0)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Overall Score", f"{overall_score}/10")
        with col2: st.metric("Clarity", f"{automation_analysis.get('clarity_score', 0)}/10")
        with col3: st.metric("Determinism", f"{automation_analysis.get('determinism_score', 0)}/10")
        with col4: st.metric("Feasibility", f"{automation_analysis.get('automation_feasibility_score', 0)}/10")
        
        # Processing summary
        col1, col2 = st.columns(2)
        with col1:
            parsed = results.get('parsed_content', {})
            summary = parsed.get('processing_summary', {})
            st.json({
                "Pages": parsed.get('total_pages'),
                "Text Length": f"{summary.get('total_text_length', 0):,}",
                "Images": summary.get('total_images', 0),
                "Chunks": automation_analysis.get('chunks_analyzed')
            })
        with col2:
            auto_summary = results.get('automation_commands', {}).get('automation_summary', {})
            st.json({
                "Total Steps": auto_summary.get('total_steps'),
                "Automatable": auto_summary.get('automatable_steps'),
                "UI Steps": auto_summary.get('ui_only_steps'),
                "Automation %": f"{auto_summary.get('automation_percentage', 0):.1f}%"
            })
    
    # Tab 2: Parsed Content
    with tabs[1]:
        st.header("📄 Parsed Content")
        parsed = results.get('parsed_content', {})
        st.text_area("Raw Text", parsed.get('combined_text', ''), height=400, disabled=True)
        
        if parsed.get('image_analysis'):
            st.subheader("🖼️ Images")
            for img in parsed['image_analysis'][:5]:  # Show first 5
                with st.expander(f"Page {img['page']} - Image {img['image_index']}"):
                    st.json(img)
    
    # Tab 3: Cleaned Content
    with tabs[2]:
        st.header("🧹 Cleaned Content")
        cleaned = results.get('cleaned_content', {})
        st.text_area("Cleaned Text", cleaned.get('cleaned_text', ''), height=400, disabled=True)
        
        st.subheader("📊 Stats")
        stats = cleaned.get('cleaning_stats', {})
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Original", f"{stats.get('original_length', 0):,}")
        with col2: st.metric("Cleaned", f"{stats.get('cleaned_length', 0):,}")
        with col3: st.metric("Reduction", f"{stats.get('reduction_percentage', 0):.1f}%")
    
    # Tab 4: Automation Analysis (NEW VAGUE TERMS SECTION)
    with tabs[3]:
        st.header("🤖 Automation Analysis")
        analysis = results.get('automation_analysis', {})
        
        # 5-metric scores
        st.subheader("📊 5-Metric Scores")
        scores = {
            "Clarity": analysis.get('clarity_score'),
            "Determinism": analysis.get('determinism_score'),
            "Logic": analysis.get('logic_decision_score'),
            "Feasibility": analysis.get('automation_feasibility_score'),
            "Observability": analysis.get('observability_score')
        }
        st.bar_chart(scores)
        
        st.divider()
        
        # NEW: Quality Flags Section
        st.subheader("🔍 Quality Flags & Issues")
        rule_data = analysis.get('rule_data', {})
        quality_flags = rule_data.get('quality_flags', {})
        logic_structure = rule_data.get('logic_structure', {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            # VAGUE TERMS
            st.markdown("### ⚠️ Vague Terms")
            vague_count = quality_flags.get('vague_terms', 0)
            st.metric("Count", vague_count)
            
            with st.expander(f"View {vague_count} Vague Terms", expanded=(vague_count > 0)):
                vague_terms = quality_flags.get('vague_terms_list', [])
                if vague_terms:
                    for i, term in enumerate(vague_terms, 1):
                        st.warning(f"{i}. **{term}**")
                else:
                    st.success("✅ No vague terms found")
            
            # UI INTERACTIONS
            st.markdown("### 🖱️ UI Interactions")
            ui_count = quality_flags.get('ui_interactions', 0)
            st.metric("Count", ui_count)
            
            with st.expander(f"View {ui_count} UI Interactions", expanded=False):
                ui_list = quality_flags.get('ui_interactions_list', [])
                if ui_list:
                    for i, interaction in enumerate(ui_list, 1):
                        st.info(f"{i}. **{interaction}**")
                else:
                    st.success("✅ No UI interactions")
        
        with col2:
            # MANUAL DECISIONS
            st.markdown("### 👤 Manual Decisions")
            manual_count = quality_flags.get('manual_decisions', 0)
            st.metric("Count", manual_count)
            
            with st.expander(f"View {manual_count} Manual Decisions", expanded=(manual_count > 0)):
                manual_list = quality_flags.get('manual_decisions_list', [])
                if manual_list:
                    for i, decision in enumerate(manual_list, 1):
                        st.error(f"{i}. **{decision}**")
                else:
                    st.success("✅ No manual decisions required")
            
            # DECISION POINTS
            st.markdown("### 🔀 Decision Points")
            decision_count = logic_structure.get('decision_points', 0)
            st.metric("Count", decision_count)
            
            with st.expander(f"View {decision_count} Decision Points", expanded=False):
                decision_list = logic_structure.get('decision_list', [])
                if decision_list:
                    for i, decision in enumerate(decision_list, 1):
                        st.info(f"{i}. **{decision}**")
                else:
                    st.info("No decision points found")
        
        # Recommendations
        st.divider()
        st.subheader("💡 Recommendations")
        recs = analysis.get('improvement_recommendations', [])
        for i, rec in enumerate(recs[:10], 1):
            st.write(f"{i}. {rec}")
    
    # Tab 5: Similar Automations
    with tabs[4]:
        st.header("🔍 Similar Automations")
        similarity = results.get('similarity_matches', {})
        st.text_area("Summary", similarity.get('document_summary', ''), height=200)
        
        matches = similarity.get('similar_automations', [])
        if matches:
            for match in matches:
                with st.expander(f"{match.get('automation_name')} ({match.get('similarity_percentage'):.1f}%)"):
                    st.json(match)
        else:
            st.info("No similar automations found")
    
    # Tab 6: Improved Document
    with tabs[5]:
        st.header("✨ Improved Document")
        improved = results.get('improved_document', {})
        st.text_area("Improved Content", improved.get('improved_content', ''), height=400)
        
        if improved.get('improved_content'):
            st.download_button(
                "⬇️ Download Improved",
                improved['improved_content'],
                "improved_document.txt"
            )
    
    # Tab 7: Generated Script
    with tabs[6]:
        st.header("📜 Generated Script")
        script = results.get('generated_script', {})
        
        if script.get('automation_viable'):
            st.success("✅ Script Generated!")
            st.code(script.get('code', ''), language='python')
            
            st.download_button(
                "⬇️ Download Script",
                script.get('code', ''),
                "automation_script.py"
            )
        else:
            st.warning("⚠️ Not enough automation potential")
            st.markdown(script.get('explanation', ''))

# Clear results button
if st.session_state.get('results'):
    if st.button("🗑️ Clear Results"):
        for key in ['results', 'processing', 'pdf_path']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
