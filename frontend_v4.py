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
if 'workflow_mode' not in st.session_state:
    st.session_state.workflow_mode = 'full_automation'

# Simple hardcoded config
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

# Workflow Mode Selector
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

# Display selected mode info
if st.session_state.workflow_mode == 'full_automation':
    st.info("""
    **🤖 Full Automation Analysis Mode**
    - Extract and clean document content
    - Analyze automation readiness with 5-metric scoring
    - Find similar automations in database
    - Generate automation commands
    - Create Python automation scripts
    
    *Best for: Runbooks, automation procedures, technical workflows*
    """)
else:
    st.success("""
    **📝 Content Quality Improvement Mode**
    - Extract and clean document content
    - Analyze content quality (Clarity, Completeness, Accuracy, Consistency, Readability, Organization)
    - Identify vague terms, unclear statements, missing details, and inconsistencies
    - Generate improved, clearer document version with specific remediation
    
    *Best for: General documents, policies, procedures, reports, manuals needing quality improvements*
    """)

st.divider()

# Input selection
st.markdown("### Choose Input Method")
input_mode = st.radio(
    "Select how you want to provide your document:",
    options=['Upload PDF File', 'Paste/Type Text'],
    horizontal=True,
    help="Choose whether to upload a PDF or directly paste/type your document content"
)

uploaded_file = None
text_input = None
tmp_file_path = None

# PDF Upload Section
if input_mode == 'Upload PDF File':
    st.markdown("### 📤 Upload PDF Document")
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload a PDF document to analyze"
    )
    
    if uploaded_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name
        
        st.success(f"✅ File uploaded: **{uploaded_file.name}**")
        
        # PDF Preview
        st.markdown("#### 📄 Document Preview")
        pdf_viewer(uploaded_file.getvalue(), width=700, height=400, annotations=[], render_text=True)

# Text Input Section
else:
    st.markdown("### 📝 Paste or Type Your Document")
    text_input = st.text_area(
        "Paste your document content here",
        height=400,
        placeholder="""Paste your document content here...

Example:
This policy outlines the procedures for...
1. Review all prerequisites
2. Follow the steps carefully
3. Ensure compliance with regulations
...""",
        help="Paste or type your document content for analysis"
    )
    
    if text_input and len(text_input.strip()) >= 50:
        word_count = len(text_input.split())
        char_count = len(text_input)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Characters", f"{char_count:,}")
        with col2:
            st.metric("Words", f"{word_count:,}")
        with col3:
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
        st.warning("⚠️ Please paste at least 50 characters of text for meaningful analysis")

# Process Button
if ((input_mode == 'Upload PDF File' and uploaded_file is not None) or 
    (input_mode == 'Paste/Type Text' and text_input and len(text_input.strip()) >= 50)):
    
    button_label = "🤖 Analyze for Automation" if st.session_state.workflow_mode == 'full_automation' else "📝 Analyze Content Quality"
    
    if st.button(button_label, type="primary", use_container_width=True):
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
                st.success("✅ Analysis complete! View results in the tabs below.")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error processing document: {str(e)}")
                st.exception(e)

# Display Results
if st.session_state.results:
    results = st.session_state.results
    workflow_mode = results.get('workflow_mode', 'full_automation')
    
    # Dynamic tab creation based on workflow mode
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
    
    # TAB 1: Raw Extracted Content (SAME FOR BOTH MODES)
    with tab1:
        st.subheader("📄 Raw Extracted Content")
        
        if 'processing_summary' in results['parsed_content']:
            summary = results['parsed_content']['processing_summary']
            
            if input_mode == 'Upload PDF File':
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Pages", results['parsed_content'].get('total_pages', 0))
                with col2:
                    st.metric("Pages with Images", summary.get('pages_with_images', 0))
                with col3:
                    st.metric("Total Images", summary.get('total_images', 0))
                with col4:
                    st.metric("Raw Text Length", f"{summary.get('total_text_length', 0):,} chars")
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Input Type", "Text Input")
                with col2:
                    st.metric("Content Length", f"{summary.get('total_text_length', 0):,} chars")
                with col3:
                    st.metric("Processing Method", "Direct Text")
        
        st.markdown("#### 📋 Complete Raw Extracted Content")
        st.text_area(
            label="Raw Content Display",
            value=results['parsed_content']['combined_text'],
            height=400,
            disabled=True,
            help="This shows all raw content from your document",
            label_visibility="hidden"
        )
        
        # Page Breakdown (PDF only)
        if input_mode == 'Upload PDF File' and 'page_breakdown' in results['parsed_content']:
            st.markdown("#### 📊 Page Processing Details")
            df_pages = pd.DataFrame(results['parsed_content']['page_breakdown'])
            st.dataframe(df_pages, use_container_width=True)
        
        # Image Analysis Display
        if input_mode == 'Upload PDF File' and 'image_analysis' in results['parsed_content'] and results['parsed_content']['image_analysis']:
            st.divider()
            st.markdown("#### 🖼️ Multimodal Image Analysis Results")
            image_analyses = results['parsed_content']['image_analysis']
            st.info(f"📸 Processed **{len(image_analyses)}** images using GPT-4o mini multimodal capabilities")
            
            with st.expander(f"🔍 View All {len(image_analyses)} Image Analysis Results", expanded=False):
                for i, img_analysis in enumerate(image_analyses, 1):
                    st.markdown(f"### 🖼️ Image {i} - Page {img_analysis.get('page', 'Unknown')}")
                    
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.markdown("**📝 Extracted Text:**")
                        extracted_text = img_analysis.get('extracted_text', 'No text found')
                        if extracted_text.strip():
                            st.code(extracted_text)
                        else:
                            st.info("No text detected in image")
                        
                        st.markdown("**📄 Image Description:**")
                        st.write(img_analysis.get('image_description', 'No description available'))
                    
                    with col2:
                        st.markdown("**🎯 Purpose in Document:**")
                        st.write(img_analysis.get('purpose', 'Purpose not determined'))
                        
                        st.markdown("**⚙️ Automation Relevance:**")
                        automation_relevance = img_analysis.get('automation_relevance', 'Not assessed')
                        if 'automation' in automation_relevance.lower():
                            st.success(f"✅ {automation_relevance}")
                        else:
                            st.info(f"ℹ️ {automation_relevance}")
                    
                    if i < len(image_analyses):
                        st.markdown("---")
    
    # TAB 2: Cleaned Content (SAME FOR BOTH MODES)
    with tab2:
        st.subheader("🧹 Cleaned & Processed Content")
        
        # Cleaning Stats
        if 'cleaning_stats' in results['cleaned_content']:
            stats = results['cleaned_content']['cleaning_stats']
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Original Length", f"{stats['original_length']:,} chars")
            with col2:
                st.metric("Cleaned Length", f"{stats['cleaned_length']:,} chars")
            with col3:
                st.metric("Noise Removed", f"{stats['reduction_percentage']}%")
            with col4:
                st.metric("Sections Found", stats['sections_identified'])
        
        # Content Cleaning Applied
        if 'removed_elements' in results['cleaned_content']:
            st.divider()
            st.markdown("#### ✅ Content Cleaning Applied")
            removed = results['cleaned_content']['removed_elements']
            col1, col2 = st.columns(2)
            with col1:
                if removed.get('headers_footers'):
                    st.success("✅ Headers & Footers Removed")
                if removed.get('page_numbers'):
                    st.success("✅ Page Numbers Removed")
            with col2:
                if removed.get('ocr_noise'):
                    st.success("✅ OCR Noise Removed")
                if removed.get('repetitive_content'):
                    st.success("✅ Repetitive Content Removed")
        
        st.divider()
        st.markdown("#### 📄 Cleaned Content Ready for Analysis")
        cleaned_content = results['cleaned_content'].get('cleaned_text', 'No cleaned content available')
        st.text_area(
            label="Cleaned Content Display",
            value=cleaned_content,
            height=350,
            disabled=True,
            help="This is the cleaned content with headers, footers, OCR noise, and irrelevant text removed",
            label_visibility="hidden"
        )
        
        # Structured Content Sections
        if 'structured_content' in results['cleaned_content']:
            structured = results['cleaned_content']['structured_content']
            
            st.divider()
            st.markdown("#### 📚 Key Sections Identified")
            
            # Process Descriptions
            if structured.get('sections', {}).get('process_descriptions'):
                st.markdown("##### 🔄 Process Descriptions")
                process_descriptions = structured['sections']['process_descriptions']
                st.info(f"Found {len(process_descriptions)} process descriptions")
                with st.expander(f"📋 View All {len(process_descriptions)} Process Descriptions", expanded=False):
                    for i, desc in enumerate(process_descriptions, 1):
                        st.markdown(f"**{i}.** {desc}")
                        if i < len(process_descriptions):
                            st.markdown("---")
            
            # Task Instructions
            if structured.get('sections', {}).get('task_instructions'):
                st.markdown("##### ✅ Task Instructions")
                task_instructions = structured['sections']['task_instructions']
                st.info(f"Found {len(task_instructions)} task instructions")
                with st.expander(f"📋 View All {len(task_instructions)} Task Instructions", expanded=False):
                    for i, task in enumerate(task_instructions, 1):
                        st.markdown(f"**{i}.** {task}")
                        if i < len(task_instructions):
                            st.markdown("---")
            
            # Key Phrases
            if structured.get('key_phrases'):
                st.divider()
                st.markdown("#### 🔑 AI-Extracted Key Phrases")
                phrases = ", ".join([f"**{phrase}**" for phrase in structured['key_phrases']])
                st.success(phrases)
                st.caption(f"AI identified {len(structured['key_phrases'])} key terms from the document")
    
    # TAB 3: Analysis (DIFFERENT FOR EACH MODE)
    with tab3:
        if workflow_mode == 'content_improvement':
            # NEW: Content Quality Analysis Tab
            st.subheader("📊 Content Quality Analysis")
            analysis = results['automation_analysis']
            quality_scores = analysis.get('quality_scores', {})
            quality_issues = analysis.get('quality_issues', {})
            overall_quality = analysis.get('overall_quality', {})
            
            # Overall Quality Score
            st.markdown("#### 🎯 Overall Content Quality Score")
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                overall_score = overall_quality.get('overall_score', 5.0)
                rating = overall_quality.get('quality_rating', 'Fair')
                rating_color = overall_quality.get('rating_color', 'info')
                
                if rating_color == 'success':
                    st.success(f"### 🌟 {overall_score}/10 - {rating}")
                elif rating_color == 'info':
                    st.info(f"### 👍 {overall_score}/10 - {rating}")
                elif rating_color == 'warning':
                    st.warning(f"### ⚠️ {overall_score}/10 - {rating}")
                else:
                    st.error(f"### ❌ {overall_score}/10 - {rating}")
            
            with col2:
                st.metric("Issues Found", overall_quality.get('total_issues_found', 0), 
                         delta=None, delta_color="inverse")
            
            with col3:
                st.metric("Avg Dimension Score", f"{overall_quality.get('average_dimension_score', 5.0):.1f}/10")
            
            st.divider()
            
            # 6 Dimension Scores
            st.markdown("#### 📏 Content Quality Dimensions (6 Metrics)")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                clarity_score = quality_scores.get('clarity_score', 5)
                st.metric("📝 Clarity", f"{clarity_score}/10", 
                         help="How clear and unambiguous is the language?")
                
                completeness_score = quality_scores.get('completeness_score', 5)
                st.metric("📚 Completeness", f"{completeness_score}/10",
                         help="How thorough and comprehensive is the content?")
            
            with col2:
                accuracy_score = quality_scores.get('accuracy_score', 5)
                st.metric("🎯 Accuracy", f"{accuracy_score}/10",
                         help="How factually correct and precise is the information?")
                
                consistency_score = quality_scores.get('consistency_score', 5)
                st.metric("🔄 Consistency", f"{consistency_score}/10",
                         help="How uniform is terminology and style?")
            
            with col3:
                readability_score = quality_scores.get('readability_score', 5)
                st.metric("👁️ Readability", f"{readability_score}/10",
                         help="How easy is it to read and comprehend?")
                
                organization_score = quality_scores.get('organization_score', 5)
                st.metric("🗂️ Organization", f"{organization_score}/10",
                         help="How well-structured and logically organized?")
            
            st.divider()
            
            # Detailed Reasoning
            st.markdown("#### 📖 Detailed Quality Analysis")
            
            with st.expander("📝 Clarity Analysis", expanded=False):
                st.write(quality_scores.get('clarity_reasoning', 'Analysis pending...'))
            
            with st.expander("📚 Completeness Analysis", expanded=False):
                st.write(quality_scores.get('completeness_reasoning', 'Analysis pending...'))
            
            with st.expander("🎯 Accuracy Analysis", expanded=False):
                st.write(quality_scores.get('accuracy_reasoning', 'Analysis pending...'))
            
            with st.expander("🔄 Consistency Analysis", expanded=False):
                st.write(quality_scores.get('consistency_reasoning', 'Analysis pending...'))
            
            with st.expander("👁️ Readability Analysis", expanded=False):
                st.write(quality_scores.get('readability_reasoning', 'Analysis pending...'))
            
            with st.expander("🗂️ Organization Analysis", expanded=False):
                st.write(quality_scores.get('organization_reasoning', 'Analysis pending...'))
            
            st.divider()
            
            # Recommendations
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 💡 Improvement Recommendations")
                if 'improvement_recommendations' in quality_scores:
                    for i, rec in enumerate(quality_scores['improvement_recommendations'], 1):
                        st.markdown(f"**{i}.** {rec}")
                else:
                    st.info("No recommendations available")
                
                if 'quick_wins' in quality_scores and quality_scores['quick_wins']:
                    st.markdown("#### ⚡ Quick Wins")
                    for win in quality_scores['quick_wins']:
                        st.success(f"✅ {win}")
            
            with col2:
                if 'critical_issues' in quality_scores and quality_scores['critical_issues']:
                    st.markdown("#### 🚨 Critical Issues")
                    for issue in quality_scores['critical_issues']:
                        st.error(f"❌ {issue}")
            
            st.divider()
            
            # Quality Issues Section
            st.markdown("#### 🔍 Specific Content Quality Issues")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # VAGUE TERMS WITH REMEDIATION
                st.markdown("##### ⚠️ Vague Terms & Remediation")
                vague_count = len(quality_issues.get('vague_terms', []))
                st.metric("Count", vague_count)
                
                vague_term_remediation = quality_issues.get('vague_term_remediation', [])
                
                if vague_term_remediation:
                    with st.expander(f"🔧 View {len(vague_term_remediation)} Vague Terms with Remediation", expanded=True):
                        for i, remediation in enumerate(vague_term_remediation, 1):
                            severity = remediation.get('severity', 'Medium')
                            if severity == 'High':
                                st.error(f"🔴 **Vague Term {i}** - High Severity")
                            elif severity == 'Medium':
                                st.warning(f"🟡 **Vague Term {i}** - Medium Severity")
                            else:
                                st.info(f"🔵 **Vague Term {i}** - Low Severity")
                            
                            st.markdown(f"**📌 Vague Term:**")
                            st.code(remediation.get('vague_term', 'N/A'), language=None)
                            
                            st.markdown(f"**❓ Why It's Vague:**")
                            st.write(remediation.get('why_vague', 'Not specified'))
                            
                            st.markdown(f"**✅ Suggested Replacement:**")
                            st.success(remediation.get('suggested_replacement', 'No suggestion'))
                            
                            st.markdown(f"**💡 Example:**")
                            st.info(remediation.get('example', 'No example'))
                            
                            if i < len(vague_term_remediation):
                                st.markdown("---")
                        
                        # Download remediation guide
                        remediation_text = "# Vague Terms Remediation Guide\n\n"
                        for i, rem in enumerate(vague_term_remediation, 1):
                            remediation_text += f"## {i}. {rem.get('vague_term', 'N/A')}\n\n"
                            remediation_text += f"**Severity:** {rem.get('severity', 'Medium')}\n\n"
                            remediation_text += f"**Why It's Vague:** {rem.get('why_vague', 'N/A')}\n\n"
                            remediation_text += f"**Suggested Replacement:** {rem.get('suggested_replacement', 'N/A')}\n\n"
                            remediation_text += f"**Example:** {rem.get('example', 'N/A')}\n\n"
                            remediation_text += "---\n\n"
                        
                        st.download_button(
                            label="📥 Download Remediation Guide",
                            data=remediation_text,
                            file_name="vague_terms_remediation_guide.md",
                            mime="text/markdown"
                        )
                else:
                    st.success("✅ No vague terms found!")
                
                # UNCLEAR STATEMENTS
                st.markdown("##### 🤔 Unclear Statements")
                unclear_count = len(quality_issues.get('unclear_statements', []))
                st.metric("Count", unclear_count)
                
                unclear_statements = quality_issues.get('unclear_statements', [])
                if unclear_statements:
                    with st.expander(f"📋 View {len(unclear_statements)} Unclear Statements", expanded=False):
                        for i, statement in enumerate(unclear_statements, 1):
                            st.write(f"**{i}.** {statement}")
                else:
                    st.success("✅ All statements are clear!")
                
                # GRAMMAR ISSUES
                st.markdown("##### 📝 Grammar & Phrasing Issues")
                grammar_count = len(quality_issues.get('grammar_issues', []))
                st.metric("Count", grammar_count)
                
                grammar_issues = quality_issues.get('grammar_issues', [])
                if grammar_issues:
                    with st.expander(f"📋 View {len(grammar_issues)} Grammar Issues", expanded=False):
                        for i, issue in enumerate(grammar_issues, 1):
                            st.write(f"**{i}.** {issue}")
                else:
                    st.success("✅ No grammar issues found!")
            
            with col2:
                # MISSING DETAILS
                st.markdown("##### 📝 Missing Details")
                missing_count = len(quality_issues.get('missing_details', []))
                st.metric("Count", missing_count)
                
                missing_details = quality_issues.get('missing_details', [])
                if missing_details:
                    with st.expander(f"📋 View {len(missing_details)} Areas Needing More Detail", expanded=False):
                        for i, detail in enumerate(missing_details, 1):
                            st.write(f"**{i}.** {detail}")
                else:
                    st.success("✅ Document is complete!")
                
                # INCONSISTENCIES
                st.markdown("##### ⚖️ Inconsistencies")
                inconsistent_count = len(quality_issues.get('inconsistencies', []))
                st.metric("Count", inconsistent_count)
                
                inconsistencies = quality_issues.get('inconsistencies', [])
                if inconsistencies:
                    with st.expander(f"📋 View {len(inconsistencies)} Inconsistencies", expanded=False):
                        for i, inconsistency in enumerate(inconsistencies, 1):
                            st.write(f"**{i}.** {inconsistency}")
                else:
                    st.success("✅ No inconsistencies detected!")
                
                # REDUNDANCIES
                st.markdown("##### 🔁 Redundancies")
                redundancy_count = len(quality_issues.get('redundancies', []))
                st.metric("Count", redundancy_count)
                
                redundancies = quality_issues.get('redundancies', [])
                if redundancies:
                    with st.expander(f"📋 View {len(redundancies)} Redundant Content", expanded=False):
                        for i, redundancy in enumerate(redundancies, 1):
                            st.write(f"**{i}.** {redundancy}")
                else:
                    st.success("✅ No redundant content found!")
        
        else:
            # EXISTING: Full Automation Analysis Tab (UNCHANGED FROM PREVIOUS VERSION)
            st.subheader("🤖 Comprehensive Runbook Analysis")
            analysis = results['automation_analysis']
            
            # Automation Readiness Scores
            st.markdown("#### 📊 Automation Readiness Scores")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                clarity_score = analysis.get('clarity_score', 5)
                st.metric("Clarity", f"{clarity_score}/10")
            with col2:
                determinism_score = analysis.get('determinism_score', 5)
                st.metric("Determinism", f"{determinism_score}/10")
            with col3:
                logic_score = analysis.get('logic_decision_score', 5)
                st.metric("Logic Structure", f"{logic_score}/10")
            with col4:
                feasibility_score = analysis.get('automation_feasibility_score', 5)
                st.metric("Automation Feasibility", f"{feasibility_score}/10")
            with col5:
                observability_score = analysis.get('observability_score', 5)
                st.metric("Observability", f"{observability_score}/10")
            
            overall_score = analysis.get('overall_automation_score', 5.0)
            st.metric("📈 Overall Automation Score", f"{overall_score}/10")
            
            st.divider()
            
            # Detailed Scoring Analysis
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📝 Detailed Scoring Analysis")
                
                st.markdown("**🎯 Clarity Analysis:**")
                st.write(analysis.get('clarity_reasoning', 'Analysis pending...'))
                
                st.markdown("**🔄 Determinism Analysis:**")
                st.write(analysis.get('determinism_reasoning', 'Analysis pending...'))
                
                st.markdown("**⚙️ Automation Feasibility:**")
                st.write(analysis.get('automation_feasibility_reasoning', 'Analysis pending...'))
            
            with col2:
                st.markdown("#### 💡 Improvement Recommendations")
                
                if 'improvement_recommendations' in analysis:
                    for i, rec in enumerate(analysis['improvement_recommendations'], 1):
                        st.markdown(f"**{i}.** {rec}")
                
                if 'critical_issues' in analysis and analysis['critical_issues']:
                    st.markdown("#### 🚨 Critical Issues")
                    for issue in analysis['critical_issues']:
                        st.error(f"❌ {issue}")
                
                if 'quick_wins' in analysis and analysis['quick_wins']:
                    st.markdown("#### ⚡ Quick Wins")
                    for win in analysis['quick_wins']:
                        st.success(f"✅ {win}")
            
            st.divider()
            
            # Quality Flags Section
            st.markdown("#### 🔍 Quality Flags & Issues")
            rule_data = analysis.get('rule_data', {})
            quality_flags = rule_data.get('quality_flags', {})
            
            col1, col2 = st.columns(2)
            
            with col1:
                # VAGUE TERMS WITH REMEDIATION
                st.markdown("##### ⚠️ Vague Terms & Remediation")
                vague_count = quality_flags.get('vague_terms', 0)
                st.metric("Count", vague_count)
                
                vague_term_remediation = quality_flags.get('vague_term_remediation', [])
                
                if vague_term_remediation:
                    with st.expander(f"🔧 View {len(vague_term_remediation)} Vague Terms", expanded=False):
                        for i, remediation in enumerate(vague_term_remediation, 1):
                            severity = remediation.get('severity', 'Medium')
                            if severity == 'High':
                                st.error(f"🔴 **Vague Term {i}** - High Severity")
                            elif severity == 'Medium':
                                st.warning(f"🟡 **Vague Term {i}** - Medium Severity")
                            else:
                                st.info(f"🔵 **Vague Term {i}** - Low Severity")
                            
                            st.markdown(f"**📌 Vague Term:**")
                            st.code(remediation.get('vague_term', 'N/A'), language=None)
                            
                            st.markdown(f"**❓ Why It's Vague:**")
                            st.write(remediation.get('why_vague', 'Not specified'))
                            
                            st.markdown(f"**✅ Suggested Replacement:**")
                            st.success(remediation.get('suggested_replacement', 'No suggestion'))
                            
                            st.markdown(f"**💡 Example:**")
                            st.info(remediation.get('example', 'No example'))
                            
                            if i < len(vague_term_remediation):
                                st.markdown("---")
                        
                        # Download button
                        remediation_text = "# Vague Terms Remediation Guide\n\n"
                        for i, rem in enumerate(vague_term_remediation, 1):
                            remediation_text += f"## {i}. {rem.get('vague_term', 'N/A')}\n\n"
                            remediation_text += f"**Severity:** {rem.get('severity', 'Medium')}\n\n"
                            remediation_text += f"**Why It's Vague:** {rem.get('why_vague', 'N/A')}\n\n"
                            remediation_text += f"**Suggested Replacement:** {rem.get('suggested_replacement', 'N/A')}\n\n"
                            remediation_text += f"**Example:** {rem.get('example', 'N/A')}\n\n"
                            remediation_text += "---\n\n"
                        
                        st.download_button(
                            label="📥 Download Remediation Guide",
                            data=remediation_text,
                            file_name="vague_terms_remediation.md",
                            mime="text/markdown"
                        )
                else:
                    st.success("✅ No vague terms found!")
                
                # UI INTERACTIONS
                st.markdown("##### 🖱️ UI Interactions")
                ui_count = quality_flags.get('ui_interactions', 0)
                st.metric("Count", ui_count)
                
                with st.expander(f"📋 View {ui_count} UI Interactions", expanded=False):
                    ui_list = quality_flags.get('ui_interactions_list', [])
                    if ui_list:
                        for i, interaction in enumerate(ui_list, 1):
                            st.write(f"**{i}.** {interaction}")
                    else:
                        st.success("✅ No UI-only interactions!")
            
            with col2:
                # MANUAL DECISIONS
                st.markdown("##### 👤 Manual Decisions")
                manual_count = quality_flags.get('manual_decisions', 0)
                st.metric("Count", manual_count)
                
                with st.expander(f"📋 View {manual_count} Manual Decisions", expanded=False):
                    manual_list = quality_flags.get('manual_decisions_list', [])
                    if manual_list:
                        for i, decision in enumerate(manual_list, 1):
                            st.write(f"**{i}.** {decision}")
                    else:
                        st.success("✅ No manual decisions!")
                
                # DECISION POINTS
                st.markdown("##### 🔀 Decision Logic Points")
                logic_structure = rule_data.get('logic_structure', {})
                decision_count = logic_structure.get('decision_points', 0)
                st.metric("Count", decision_count)
                
                with st.expander(f"📋 View {decision_count} Decision Points", expanded=False):
                    decision_list = logic_structure.get('decision_list', [])
                    if decision_list:
                        for i, decision in enumerate(decision_list, 1):
                            st.write(f"**{i}.** {decision}")
                    else:
                        st.info("No decision points found")
            
            # Commands Section
            st.divider()
            st.markdown("#### 💻 Commands Found")
            commands_data = rule_data.get('commands', {})
            st.metric("Total Commands", commands_data.get('total_commands', 0))
            
            with st.expander("📋 View All Commands", expanded=False):
                command_types = commands_data.get('command_types', [])
                if command_types:
                    for i, cmd in enumerate(command_types[:20], 1):
                        st.code(cmd, language=None)
                    if len(command_types) > 20:
                        st.info(f"... and {len(command_types) - 20} more commands")
                else:
                    st.info("No commands found")
    
    # TAB 4: Similar Automations OR Improved Document (depends on mode)
    with tab4:
        if workflow_mode == 'content_improvement':
            # Improved Document for Content Mode
            st.subheader("✨ AI-Improved Document")
            
            improved = results.get('improved_document', {})
            
            if improved:
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown("#### 📝 Enhanced Content")
                    with st.expander("📄 View Improved Document", expanded=True):
                        improved_content = improved.get('improved_content', 'No improved content')
                        st.text_area(
                            "Improved Content",
                            value=improved_content,
                            height=500,
                            disabled=True,
                            label_visibility="hidden"
                        )
                
                with col2:
                    st.markdown("#### 📈 Quality Improvements")
                    
                    quality_increase = improved.get('quality_score_increase', 0)
                    st.metric("Quality Score Increase", f"+{quality_increase:.1f}")
                    
                    st.write("**New Scores:**")
                    st.metric("Clarity", f"{improved.get('new_clarity_score', 0):.1f}/10")
                    st.metric("Completeness", f"{improved.get('new_completeness_score', 0):.1f}/10")
                    st.metric("Readability", f"{improved.get('new_readability_score', 0):.1f}/10")
                    st.metric("Organization", f"{improved.get('new_organization_score', 0):.1f}/10")
                
                st.divider()
                
                st.markdown("#### 🔧 List of Improvements")
                improvements_made = improved.get('improvements_made', [])
                
                if improvements_made:
                    for i, improvement in enumerate(improvements_made, 1):
                        st.write(f"✅ **{i}.** {improvement}")
                else:
                    st.info("No specific improvements listed")
                
                # Download button
                if improved.get('improved_content'):
                    st.download_button(
                        label="⬇️ Download Improved Document",
                        data=improved.get('improved_content', ''),
                        file_name="improved_document.txt",
                        mime="text/plain"
                    )
            else:
                st.info("No improved document available")
        
        else:
            # Similar Automations Tab (UNCHANGED)
            st.subheader("🔍 Similar Existing Automations")
            
            if 'similarity_matches' in results and results['similarity_matches']:
                similarity_data = results['similarity_matches']
                
                if similarity_data.get('skipped'):
                    st.info(f"ℹ️ {similarity_data.get('reason', 'Similarity matching not performed')}")
                elif 'error' in similarity_data:
                    st.warning(f"⚠️ Similarity matching unavailable: {similarity_data['error']}")
                else:
                    st.markdown("#### 📄 Document Summary")
                    st.info(similarity_data.get('document_summary', 'No summary'))
                    
                    similar_automations = similarity_data.get('similar_automations', [])
                    
                    if similar_automations:
                        st.markdown(f"#### 🎯 Top {len(similar_automations)} Similar Automations")
                        
                        for i, automation in enumerate(similar_automations, 1):
                            similarity_pct = automation.get('similarity_percentage', 0)
                            
                            if similarity_pct >= 80:
                                color = "🟢"
                            elif similarity_pct >= 60:
                                color = "🟡"
                            else:
                                color = "🔴"
                            
                            with st.expander(f"{color} **{i}. {automation.get('automation_name', 'Unknown')}** - {similarity_pct}% Similar", expanded=(i == 1)):
                                st.markdown(f"**Description:** {automation.get('description', 'N/A')}")
                                st.markdown("**Steps:**")
                                st.text_area("Steps", value=automation.get('steps', 'N/A'), height=200, disabled=True, key=f"sim_{i}", label_visibility="collapsed")
                    else:
                        st.info("ℹ️ No similar automations found")
    
    # Remaining tabs only for full automation mode
    if workflow_mode == 'full_automation':
        # TAB 5: Improved Document (UNCHANGED)
        with tab5:
            st.subheader("✨ AI-Improved Document")
            
            improved = results.get('improved_document', {})
            
            if improved:
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown("#### 📝 Enhanced Content")
                    with st.expander("📄 View Improved Document", expanded=True):
                        improved_content = improved.get('improved_content', 'No improved content')
                        st.text_area("Improved Content", value=improved_content, height=500, disabled=True, label_visibility="hidden")
                
                with col2:
                    st.markdown("#### 📈 Improvements Made")
                    
                    score_increase = improved.get('automation_score_increase', 0)
                    st.metric("Score Increase", f"+{score_increase:.1f}")
                    
                    st.write("**New Scores:**")
                    st.metric("Clarity", f"{improved.get('new_clarity_score', 0):.1f}/10")
                    st.metric("Determinism", f"{improved.get('new_determinism_score', 0):.1f}/10")
                    st.metric("Feasibility", f"{improved.get('new_automation_feasibility', 0):.1f}/10")
                
                st.divider()
                
                st.markdown("#### 🔧 List of Improvements")
                improvements_made = improved.get('improvements_made', [])
                
                if improvements_made:
                    for i, improvement in enumerate(improvements_made, 1):
                        st.write(f"✅ **{i}.** {improvement}")
                
                if improved.get('improved_content'):
                    st.download_button(
                        label="⬇️ Download Improved Document",
                        data=improved.get('improved_content', ''),
                        file_name="improved_document.txt",
                        mime="text/plain"
                    )
        
        # TAB 6: Generated Script (UNCHANGED)
        with tab6:
            st.subheader("📜 Generated Automation Script")
            
            script = results.get('generated_script', {})
            
            if script and not script.get('skipped'):
                script_type = script.get('script_type', 'Unknown')
                automation_viable = script.get('automation_viable', False)
                automation_pct = script.get('automation_percentage', 0)
                
                if automation_viable:
                    st.success(f"✅ **{script_type}** - Automation is viable ({automation_pct:.1f}% automatable)")
                else:
                    st.warning(f"⚠️ **{script_type}** - Automation below threshold ({automation_pct:.1f}% automatable)")
                
                st.divider()
                
                if automation_viable:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown("#### 🐍 Python Script")
                        script_code = script.get('code', '# No code generated')
                        st.code(script_code, language='python')
                        
                        st.download_button(
                            label="⬇️ Download Script",
                            data=script_code,
                            file_name="automation_script.py",
                            mime="text/x-python"
                        )
                    
                    with col2:
                        st.markdown("#### 📋 Script Information")
                        st.info(script.get('script_description', 'N/A'))
                        
                        st.markdown("**Coverage:**")
                        st.write(script.get('automation_coverage', 'N/A'))
                    
                    st.divider()
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("##### 📦 Requirements")
                        requirements = script.get('requirements', [])
                        if requirements:
                            for req in requirements:
                                st.code(req, language=None)
                    
                    with col2:
                        st.markdown("##### ▶️ Execution Steps")
                        execution_steps = script.get('execution_steps', [])
                        if execution_steps:
                            for i, step in enumerate(execution_steps, 1):
                                st.write(f"{i}. {step}")
                    
                    with col3:
                        st.markdown("##### ⚙️ Parameters Required")
                        parameters = script.get('parameters_required', [])
                        if parameters:
                            for param in parameters:
                                st.write(f"• {param}")
                    
                    st.divider()
                    
                    st.markdown("#### 👤 Manual Steps Remaining")
                    manual_steps = script.get('manual_steps_remaining', [])
                    if manual_steps:
                        st.warning("⚠️ These steps still require manual intervention:")
                        for i, step in enumerate(manual_steps, 1):
                            st.write(f"{i}. {step}")
                    else:
                        st.success("✅ All steps can be automated!")
                
                else:
                    st.markdown("#### 📊 Analysis Report")
                    explanation = script.get('explanation', 'No explanation')
                    st.text(explanation)
                    
                    st.divider()
                    st.markdown("#### 💡 Recommendations")
                    recommendations = script.get('recommendations', [])
                    if recommendations:
                        for i, rec in enumerate(recommendations, 1):
                            st.write(f"**{i}.** {rec}")
            elif script.get('skipped'):
                st.info(f"ℹ️ {script.get('reason', 'Script generation not performed in this mode')}")

# Clear results button
if st.session_state.get('results'):
    st.divider()
    if st.button("🗑️ Clear Results & Start New Analysis"):
        for key in ['results', 'processing', 'pdf_path']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
