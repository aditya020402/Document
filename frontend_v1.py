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

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Input mode selection
    st.session_state.input_mode = st.radio(
        "Input Mode",
        options=['pdf', 'text'],
        format_func=lambda x: "📄 PDF Upload" if x == 'pdf' else "📝 Text Input"
    )
    
    st.divider()
    
    # Database configuration
    with st.expander("🗄️ Database Configuration", expanded=False):
        db_host = st.text_input("Host", value="localhost")
        db_port = st.text_input("Port", value="5432")
        db_name = st.text_input("Database", value="automation_db")
        db_user = st.text_input("User", value="your_username")
        db_password = st.text_input("Password", value="your_password", type="password")
    
    st.divider()
    
    # Azure configuration
    with st.expander("☁️ Azure OpenAI Configuration", expanded=False):
        azure_endpoint = st.text_input("Azure Endpoint", value="your-azure-endpoint")
        azure_api_key = st.text_input("API Key", value="your-api-key", type="password")
        azure_api_version = st.text_input("API Version", value="2024-07-18")
        
        st.subheader("Embedding Configuration")
        embedding_endpoint = st.text_input("Embedding Endpoint", value="https://your-resource.openai.azure.com/")
        embedding_api_key = st.text_input("Embedding API Key", value="your-azure-api-key", type="password")
        embedding_deployment = st.text_input("Embedding Deployment", value="text-embedding-ada-002")
        embedding_api_version = st.text_input("Embedding API Version", value="2023-05-15")

# Main content area
if st.session_state.input_mode == 'pdf':
    st.subheader("📤 Upload PDF Document")
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload a PDF document to analyze for automation potential"
    )
    
    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.read())
            pdf_path = tmp_file.name
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"📄 Loaded: **{uploaded_file.name}** ({uploaded_file.size} bytes)")
        with col2:
            if st.button("🚀 Analyze Document", type="primary", use_container_width=True):
                st.session_state.processing = True

else:  # text mode
    st.subheader("📝 Paste Text Content")
    text_input = st.text_area(
        "Paste your document text here",
        height=300,
        placeholder="Paste your automation/runbook document text here..."
    )
    
    if text_input:
        if st.button("🚀 Analyze Text", type="primary"):
            st.session_state.processing = True
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_file:
                tmp_file.write(text_input)
                pdf_path = tmp_file.name

# Processing logic
if st.session_state.processing:
    try:
        # Initialize workflow
        db_config = {
            'dbname': db_name,
            'user': db_user,
            'password': db_password,
            'host': db_host,
            'port': db_port
        }
        
        azure_embedding_config = {
            'api_key': embedding_api_key,
            'api_version': embedding_api_version,
            'endpoint': embedding_endpoint,
            'embedding_deployment': embedding_deployment
        }
        
        workflow = DocumentAutomationWorkflow(
            db_config=db_config,
            azure_embedding_config=azure_embedding_config
        )
        
        # Process document
        with st.spinner("🔄 Processing document... This may take a few minutes."):
            if st.session_state.input_mode == 'pdf':
                results = asyncio.run(workflow.process_document(pdf_path))
            else:
                results = asyncio.run(workflow.process_text_document(pdf_path))
        
        st.session_state.results = results
        st.session_state.processing = False
        st.success("✅ Analysis complete!")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error during processing: {str(e)}")
        st.session_state.processing = False

# Display results
if st.session_state.results:
    results = st.session_state.results
    
    # Create tabs for different result sections
    tabs = st.tabs([
        "📊 Overview",
        "📄 Parsed Content",
        "🧹 Cleaned Content",
        "🤖 Automation Analysis",
        "🔍 Similar Automations",
        "✨ Improved Document",
        "📜 Generated Script"
    ])
    
    # Tab 1: Overview
    with tabs[0]:
        st.header("📊 Analysis Overview")
        
        # Key metrics
        automation_analysis = results.get('automation_analysis', {})
        overall_score = automation_analysis.get('overall_automation_score', 0)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Overall Automation Score",
                f"{overall_score}/10",
                delta=f"{overall_score - 5:.1f}" if overall_score != 5 else None
            )
        
        with col2:
            clarity_score = automation_analysis.get('clarity_score', 0)
            st.metric("Clarity Score", f"{clarity_score}/10")
        
        with col3:
            determinism_score = automation_analysis.get('determinism_score', 0)
            st.metric("Determinism Score", f"{determinism_score}/10")
        
        with col4:
            feasibility_score = automation_analysis.get('automation_feasibility_score', 0)
            st.metric("Feasibility Score", f"{feasibility_score}/10")
        
        st.divider()
        
        # Processing summary
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Processing Summary")
            parsed_summary = results.get('parsed_content', {}).get('processing_summary', {})
            
            st.write(f"**Total Pages:** {results.get('parsed_content', {}).get('total_pages', 'N/A')}")
            st.write(f"**Total Text Length:** {parsed_summary.get('total_text_length', 0):,} characters")
            st.write(f"**Images Analyzed:** {parsed_summary.get('total_images', 0)}")
            st.write(f"**Chunks Analyzed:** {automation_analysis.get('chunks_analyzed', 'N/A')}")
            st.write(f"**Chunking Method:** {automation_analysis.get('scoring_method', 'paragraph-based')}")
        
        with col2:
            st.subheader("🎯 Automation Feasibility")
            automation_commands = results.get('automation_commands', {})
            auto_summary = automation_commands.get('automation_summary', {})
            
            st.write(f"**Total Steps:** {auto_summary.get('total_steps', 0)}")
            st.write(f"**Automatable Steps:** {auto_summary.get('automatable_steps', 0)}")
            st.write(f"**UI-Only Steps:** {auto_summary.get('ui_only_steps', 0)}")
            st.write(f"**Automation Percentage:** {auto_summary.get('automation_percentage', 0):.1f}%")
            st.write(f"**Complexity Level:** {auto_summary.get('complexity_level', 'Unknown')}")
        
        st.divider()
        
        # Score breakdown
        st.subheader("📊 Detailed Score Breakdown")
        
        score_data = {
            "Metric": [
                "Clarity",
                "Determinism",
                "Logic/Decision",
                "Automation Feasibility",
                "Observability"
            ],
            "Score": [
                automation_analysis.get('clarity_score', 0),
                automation_analysis.get('determinism_score', 0),
                automation_analysis.get('logic_decision_score', 0),
                automation_analysis.get('automation_feasibility_score', 0),
                automation_analysis.get('observability_score', 0)
            ]
        }
        
        df_scores = pd.DataFrame(score_data)
        st.bar_chart(df_scores.set_index('Metric'))
    
    # Tab 2: Parsed Content
    with tabs[1]:
        st.header("📄 Parsed Content")
        
        parsed_content = results.get('parsed_content', {})
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📝 Extracted Text")
            with st.expander("View Full Text", expanded=False):
                st.text_area(
                    "Combined Text",
                    value=parsed_content.get('combined_text', 'No content'),
                    height=400,
                    disabled=True
                )
        
        with col2:
            st.subheader("📑 Page Breakdown")
            page_breakdown = parsed_content.get('page_breakdown', [])
            if page_breakdown:
                df_pages = pd.DataFrame(page_breakdown)
                st.dataframe(df_pages, use_container_width=True)
        
        # Image analysis
        st.divider()
        st.subheader("🖼️ Image Analysis Results")
        
        image_analysis = parsed_content.get('image_analysis', [])
        if image_analysis:
            for img in image_analysis:
                with st.expander(f"📸 Page {img.get('page')} - Image {img.get('image_index')}", expanded=False):
                    st.write(f"**Description:** {img.get('image_description', 'N/A')}")
                    st.write(f"**Purpose:** {img.get('purpose', 'N/A')}")
                    st.write(f"**Automation Relevance:** {img.get('automation_relevance', 'N/A')}")
                    
                    extracted_text = img.get('extracted_text', '').strip()
                    if extracted_text:
                        st.write(f"**Extracted Text:** {extracted_text}")
                    else:
                        st.write("**Extracted Text:** No text detected")
        else:
            st.info("No images found in document")
    
    # Tab 3: Cleaned Content
    with tabs[2]:
        st.header("🧹 Cleaned Content")
        
        cleaned_content = results.get('cleaned_content', {})
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("✨ Cleaned Text")
            with st.expander("View Cleaned Text", expanded=False):
                st.text_area(
                    "Cleaned Content",
                    value=cleaned_content.get('cleaned_text', 'No content'),
                    height=400,
                    disabled=True
                )
        
        with col2:
            st.subheader("📊 Cleaning Statistics")
            cleaning_stats = cleaned_content.get('cleaning_stats', {})
            
            st.metric("Original Length", f"{cleaning_stats.get('original_length', 0):,} chars")
            st.metric("Cleaned Length", f"{cleaning_stats.get('cleaned_length', 0):,} chars")
            st.metric("Reduction", f"{cleaning_stats.get('reduction_percentage', 0):.1f}%")
            st.metric("Sections Identified", cleaning_stats.get('sections_identified', 0))
            st.metric("Key Phrases Found", cleaning_stats.get('key_phrases_found', 0))
        
        # Structured content sections
        st.divider()
        st.subheader("📚 Structured Content Analysis")
        
        structured = cleaned_content.get('structured_content', {})
        sections = structured.get('sections', {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("🔄 Process Descriptions", expanded=False):
                process_list = sections.get('process_descriptions', [])
                if process_list:
                    for i, item in enumerate(process_list[:10], 1):
                        st.write(f"{i}. {item}")
                    if len(process_list) > 10:
                        st.info(f"... and {len(process_list) - 10} more")
                else:
                    st.info("No process descriptions found")
            
            with st.expander("📋 Data Definitions", expanded=False):
                data_list = sections.get('data_definitions', [])
                if data_list:
                    for i, item in enumerate(data_list[:10], 1):
                        st.write(f"{i}. {item}")
                    if len(data_list) > 10:
                        st.info(f"... and {len(data_list) - 10} more")
                else:
                    st.info("No data definitions found")
        
        with col2:
            with st.expander("✅ Task Instructions", expanded=False):
                task_list = sections.get('task_instructions', [])
                if task_list:
                    for i, item in enumerate(task_list[:10], 1):
                        st.write(f"{i}. {item}")
                    if len(task_list) > 10:
                        st.info(f"... and {len(task_list) - 10} more")
                else:
                    st.info("No task instructions found")
            
            with st.expander("🔀 Decision Rules", expanded=False):
                decision_list = sections.get('decision_rules', [])
                if decision_list:
                    for i, item in enumerate(decision_list[:10], 1):
                        st.write(f"{i}. {item}")
                    if len(decision_list) > 10:
                        st.info(f"... and {len(decision_list) - 10} more")
                else:
                    st.info("No decision rules found")
        
        # Key phrases
        st.divider()
        st.subheader("🔑 Key Phrases Extracted")
        key_phrases = structured.get('key_phrases', [])
        if key_phrases:
            # Display as badges/tags
            phrase_html = " ".join([f'<span style="background-color: #e3f2fd; padding: 5px 10px; margin: 5px; border-radius: 15px; display: inline-block;">{phrase}</span>' for phrase in key_phrases])
            st.markdown(phrase_html, unsafe_allow_html=True)
        else:
            st.info("No key phrases extracted")
    
    # Tab 4: Automation Analysis
    with tabs[3]:
        st.header("🤖 Automation Analysis")
        
        automation_analysis = results.get('automation_analysis', {})
        
        # Five-metric scores with reasoning
        st.subheader("📊 Five-Metric Analysis")
        
        metrics = [
            ("clarity", "Clarity", "📝"),
            ("determinism", "Determinism", "🎯"),
            ("logic_decision", "Logic/Decision", "🔀"),
            ("automation_feasibility", "Automation Feasibility", "⚙️"),
            ("observability", "Observability", "👁️")
        ]
        
        for metric_key, metric_name, icon in metrics:
            score = automation_analysis.get(f'{metric_key}_score', 0)
            reasoning = automation_analysis.get(f'{metric_key}_reasoning', 'No reasoning available')
            
            with st.expander(f"{icon} **{metric_name}: {score}/10**", expanded=False):
                st.write(reasoning)
                st.progress(score / 10)
        
        st.divider()
        
        # Rule data analysis
        st.subheader("📋 Rule Data Analysis")
        
        rule_data = automation_analysis.get('rule_data', {})
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 💻 Commands")
            commands_data = rule_data.get('commands', {})
            st.metric("Total Commands", commands_data.get('total_commands', 0))
            
            with st.expander("View Commands", expanded=False):
                command_types = commands_data.get('command_types', [])
                if command_types:
                    for i, cmd in enumerate(command_types[:20], 1):
                        st.code(cmd, language=None)
                    if len(command_types) > 20:
                        st.info(f"... and {len(command_types) - 20} more commands")
                else:
                    st.info("No commands found")
        
        with col2:
            st.markdown("### ⚠️ Quality Flags")
            quality_flags = rule_data.get('quality_flags', {})
            
            st.metric("Vague Terms", quality_flags.get('vague_terms', 0))
            st.metric("Manual Decisions", quality_flags.get('manual_decisions', 0))
            st.metric("UI Interactions", quality_flags.get('ui_interactions', 0))
        
        with col3:
            st.markdown("### 🔀 Logic Structure")
            logic_structure = rule_data.get('logic_structure', {})
            
            st.metric("Decision Points", logic_structure.get('decision_points', 0))
            st.metric("Conditional Statements", logic_structure.get('conditional_statements', 0))
        
        st.divider()
        
        # NEW: Detailed Quality Flags Section
        st.subheader("🔍 Detailed Quality Issues")
        
        quality_flags = rule_data.get('quality_flags', {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Vague Terms List
            with st.expander("⚠️ **Vague Terms Found** (" + str(quality_flags.get('vague_terms', 0)) + ")", expanded=True):
                vague_terms_list = quality_flags.get('vague_terms_list', [])
                if vague_terms_list:
                    st.warning("These terms are unclear and should be made more specific for automation:")
                    for i, term in enumerate(vague_terms_list, 1):
                        st.write(f"**{i}.** {term}")
                else:
                    st.success("✅ No vague terms found - document has clear terminology!")
            
            # UI Interactions List
            with st.expander("🖱️ **UI Interactions** (" + str(quality_flags.get('ui_interactions', 0)) + ")", expanded=False):
                ui_interactions_list = quality_flags.get('ui_interactions_list', [])
                if ui_interactions_list:
                    st.info("These steps require UI interaction and may be harder to automate:")
                    for i, interaction in enumerate(ui_interactions_list, 1):
                        st.write(f"**{i}.** {interaction}")
                else:
                    st.success("✅ No UI-only interactions found!")
        
        with col2:
            # Manual Decisions List
            with st.expander("👤 **Manual Decisions Required** (" + str(quality_flags.get('manual_decisions', 0)) + ")", expanded=True):
                manual_decisions_list = quality_flags.get('manual_decisions_list', [])
                if manual_decisions_list:
                    st.warning("These steps require human judgment and cannot be fully automated:")
                    for i, decision in enumerate(manual_decisions_list, 1):
                        st.write(f"**{i}.** {decision}")
                else:
                    st.success("✅ No manual decision points found!")
            
            # Decision Points List
            with st.expander("🔀 **Decision Logic Points** (" + str(logic_structure.get('decision_points', 0)) + ")", expanded=False):
                decision_list = logic_structure.get('decision_list', [])
                if decision_list:
                    st.info("Conditional logic and branching points found in the document:")
                    for i, decision in enumerate(decision_list, 1):
                        st.write(f"**{i}.** {decision}")
                else:
                    st.info("No decision points found")
        
        st.divider()
        
        # Recommendations
        st.subheader("💡 Recommendations & Issues")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### ✨ Improvement Recommendations")
            recommendations = automation_analysis.get('improvement_recommendations', [])
            if recommendations:
                for i, rec in enumerate(recommendations, 1):
                    st.write(f"{i}. {rec}")
            else:
                st.info("No recommendations available")
        
        with col2:
            st.markdown("### 🚨 Critical Issues")
            critical_issues = automation_analysis.get('critical_issues', [])
            if critical_issues:
                for i, issue in enumerate(critical_issues, 1):
                    st.write(f"{i}. {issue}")
            else:
                st.success("No critical issues found")
        
        with col3:
            st.markdown("### ⚡ Quick Wins")
            quick_wins = automation_analysis.get('quick_wins', [])
            if quick_wins:
                for i, win in enumerate(quick_wins, 1):
                    st.write(f"{i}. {win}")
            else:
                st.info("No quick wins identified")
    
    # Tab 5: Similar Automations
    with tabs[4]:
        st.header("🔍 Similar Automations")
        
        similarity_matches = results.get('similarity_matches', {})
        
        st.subheader("📄 Document Summary")
        with st.expander("View Summary", expanded=False):
            st.write(similarity_matches.get('document_summary', 'No summary available'))
        
        st.divider()
        
        st.subheader("🎯 Similar Automation Matches")
        
        similar_automations = similarity_matches.get('similar_automations', [])
        total_matches = similarity_matches.get('total_matches_found', 0)
        
        if similar_automations:
            st.info(f"Found {total_matches} similar automation(s)")
            
            for i, automation in enumerate(similar_automations, 1):
                similarity_pct = automation.get('similarity_percentage', 0)
                
                # Color code based on similarity
                if similarity_pct >= 80:
                    color = "🟢"
                elif similarity_pct >= 60:
                    color = "🟡"
                else:
                    color = "🔴"
                
                with st.expander(
                    f"{color} **{automation.get('automation_name', 'Unknown')}** - {similarity_pct:.1f}% match",
                    expanded=(i == 1)
                ):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.write("**Description:**")
                        st.write(automation.get('description', 'No description'))
                        
                        st.write("**Steps:**")
                        st.write(automation.get('steps', 'No steps available'))
                    
                    with col2:
                        st.metric("Similarity Score", f"{automation.get('similarity_score', 0):.3f}")
                        st.progress(similarity_pct / 100)
        else:
            error = similarity_matches.get('error', '')
            if error:
                st.warning(f"Similarity matching not available: {error}")
            else:
                st.info("No similar automations found")
    
    # Tab 6: Improved Document
    with tabs[5]:
        st.header("✨ Improved Document")
        
        improved_doc = results.get('improved_document', {})
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("📝 Enhanced Content")
            with st.expander("View Improved Document", expanded=True):
                improved_content = improved_doc.get('improved_content', 'No improved content available')
                st.text_area(
                    "Improved Content",
                    value=improved_content,
                    height=500,
                    disabled=True
                )
        
        with col2:
            st.subheader("📈 Improvements Made")
            
            score_increase = improved_doc.get('automation_score_increase', 0)
            st.metric("Score Increase", f"+{score_increase:.1f}")
            
            st.write("**New Scores:**")
            st.metric("Clarity", f"{improved_doc.get('new_clarity_score', 0):.1f}/10")
            st.metric("Determinism", f"{improved_doc.get('new_determinism_score', 0):.1f}/10")
            st.metric("Feasibility", f"{improved_doc.get('new_automation_feasibility', 0):.1f}/10")
        
        st.divider()
        
        st.subheader("🔧 List of Improvements")
        improvements_made = improved_doc.get('improvements_made', [])
        
        if improvements_made:
            for i, improvement in enumerate(improvements_made, 1):
                st.write(f"✅ **{i}.** {improvement}")
        else:
            st.info("No specific improvements listed")
        
        # Download button for improved content
        if improved_doc.get('improved_content'):
            st.download_button(
                label="⬇️ Download Improved Document",
                data=improved_doc.get('improved_content', ''),
                file_name="improved_document.txt",
                mime="text/plain"
            )
    
    # Tab 7: Generated Script
    with tabs[6]:
        st.header("📜 Generated Automation Script")
        
        generated_script = results.get('generated_script', {})
        
        script_type = generated_script.get('script_type', 'Unknown')
        automation_viable = generated_script.get('automation_viable', False)
        automation_pct = generated_script.get('automation_percentage', 0)
        
        # Status banner
        if automation_viable:
            st.success(f"✅ **{script_type}** - Automation is viable ({automation_pct:.1f}% automatable)")
        else:
            st.warning(f"⚠️ **{script_type}** - Automation below threshold ({automation_pct:.1f}% automatable)")
        
        st.divider()
        
        if automation_viable:
            # Script details
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("🐍 Python Script")
                
                script_code = generated_script.get('code', '# No code generated')
                st.code(script_code, language='python')
                
                # Download button
                st.download_button(
                    label="⬇️ Download Script",
                    data=script_code,
                    file_name="automation_script.py",
                    mime="text/x-python"
                )
            
            with col2:
                st.subheader("📋 Script Information")
                
                st.write("**Description:**")
                st.write(generated_script.get('script_description', 'N/A'))
                
                st.write("**Automation Coverage:**")
                st.write(generated_script.get('automation_coverage', 'N/A'))
                
                st.write("**Notes:**")
                st.write(generated_script.get('notes', 'N/A'))
            
            st.divider()
            
            # Requirements and execution
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("### 📦 Requirements")
                requirements = generated_script.get('requirements', [])
                if requirements:
                    for req in requirements:
                        st.code(req, language=None)
                else:
                    st.info("No requirements specified")
            
            with col2:
                st.markdown("### ▶️ Execution Steps")
                execution_steps = generated_script.get('execution_steps', [])
                if execution_steps:
                    for i, step in enumerate(execution_steps, 1):
                        st.write(f"{i}. {step}")
                else:
                    st.info("No execution steps provided")
            
            with col3:
                st.markdown("### ⚙️ Parameters Required")
                parameters = generated_script.get('parameters_required', [])
                if parameters:
                    for param in parameters:
                        st.write(f"• {param}")
                else:
                    st.info("No parameters required")
            
            st.divider()
            
            # Manual steps remaining
            st.subheader("👤 Manual Steps Remaining")
            manual_steps = generated_script.get('manual_steps_remaining', [])
            if manual_steps:
                st.warning("These steps still require manual intervention:")
                for i, step in enumerate(manual_steps, 1):
                    st.write(f"{i}. {step}")
            else:
                st.success("✅ All steps can be automated!")
        
        else:
            # Low automation explanation
            st.subheader("📊 Analysis Report")
            
            explanation = generated_script.get('explanation', 'No explanation available')
            st.text(explanation)
            
            st.divider()
            
            st.subheader("💡 Recommendations to Improve Automation Score")
            recommendations = generated_script.get('recommendations', [])
            if recommendations:
                for i, rec in enumerate(recommendations, 1):
                    st.write(f"**{i}.** {rec}")
            else:
                st.info("No recommendations available")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>📄 Document Automation Analyzer | Built with Streamlit, LangGraph & Azure OpenAI</p>
    <p>Powered by paragraph-based chunking and comprehensive 5-metric analysis</p>
</div>
""", unsafe_allow_html=True)
