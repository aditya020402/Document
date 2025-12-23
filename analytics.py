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

# Add link to analytics dashboard
st.markdown("""
Upload a document to analyze automation readiness or improve content quality.  
📊 **[View Token Analytics Dashboard](http://localhost:8502)** (Run: `streamlit run token_analytics_dashboard.py --server.port 8502`)
""")

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = None
if 'input_mode' not in st.session_state:
    st.session_state.input_mode = 'pdf'
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'workflow_mode' not in st.session_state:
    st.session_state.workflow_mode = 'full_automation'

# DB CONFIG
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
col1, col2 = st.columns(2)

with col1:
    if st.button(
        "🤖 Full Automation Analysis", 
        use_container_width=True,
        type="primary" if st.session_state.workflow_mode == 'full_automation' else "secondary"
    ):
        st.session_state.workflow_mode = 'full_automation'

with col2:
    if st.button(
        "📝 Content Quality Improvement", 
        use_container_width=True,
        type="primary" if st.session_state.workflow_mode == 'content_improvement' else "secondary"
    ):
        st.session_state.workflow_mode = 'content_improvement'

if st.session_state.workflow_mode == 'full_automation':
    st.info("**Full Automation Analysis**: Analyzes automation readiness, finds similar automations, generates scripts.")
else:
    st.success("**Content Quality Improvement**: Focuses on clarity, completeness, readability, and consistency.")

st.divider()

# ----------------------
# Input selection
# ----------------------

st.markdown("### Choose Input Method")
input_mode = st.radio(
    "Select input method:",
    options=['Upload PDF File', 'Paste/Type Text'],
    horizontal=True
)

uploaded_file = None
text_input = None
tmp_file_path = None

if input_mode == 'Upload PDF File':
    st.markdown("### 📤 Upload PDF Document")
    uploaded_file = st.file_uploader("Choose a PDF file", type=['pdf'])
    
    if uploaded_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name
        
        st.success(f"✅ File uploaded: **{uploaded_file.name}**")
        st.markdown("#### 📄 Document Preview")
        pdf_viewer(uploaded_file.getvalue(), width=700, height=400)

else:
    st.markdown("### 📝 Paste or Type Your Document")
    text_input = st.text_area("Paste content here", height=400, placeholder="Paste your document...")
    
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
        
        st.success(f"✅ Text ready ({word_count} words)")

# ----------------------
# Process Button
# ----------------------

if ((input_mode == 'Upload PDF File' and uploaded_file) or 
    (input_mode == 'Paste/Type Text' and text_input and len(text_input.strip()) >= 50)):
    
    label = "🤖 Analyze for Automation" if st.session_state.workflow_mode == 'full_automation' else "📝 Analyze Content Quality"
    
    if st.button(label, type="primary", use_container_width=True):
        with st.spinner(f"🔄 Processing..."):
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
                st.success("✅ Analysis complete!")
                
                # Show token usage just for this session
                token_usage = results.get('token_usage', {})
                if token_usage.get('session_id'):
                    st.info(f"📊 **Session ID: {token_usage['session_id']}** | Tokens Used: **{token_usage.get('total_tokens', 0):,}** | [View Analytics Dashboard](http://localhost:8502)")
                
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# ----------------------
# Results Display (Keep all your existing tabs)
# ----------------------

if st.session_state.results:
    results = st.session_state.results
    workflow_mode = results.get('workflow_mode', 'full_automation')
    
    # ... [Keep all your existing tab code from previous version] ...
    # Just remove the "Session Summary" section with token metrics
