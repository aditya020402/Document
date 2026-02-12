import streamlit as st
import uuid
from pathlib import Path
import os
from database import DocumentDatabase

# Initialize database
db = DocumentDatabase()

# Upload directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def main():
    st.set_page_config(page_title="KAT Bulk Upload", page_icon="📤", layout="wide")
    
    st.title("📤 KAT - Bulk Document Upload")
    st.markdown("Upload documents for automated processing")
    
    # Sidebar - User info and stats
    with st.sidebar:
        st.header("👤 User Information")
        user_email = st.text_input("Email", value="user@company.com")
        
        st.markdown("---")
        st.header("📊 Queue Status")
        stats = db.get_processing_stats()
        st.metric("Queued", stats['queued'])
        st.metric("Processing", stats['processing'])
        st.metric("Completed", stats['completed'])
        st.metric("Failed", stats['failed'])
        
        if st.button("🔄 Refresh Stats"):
            st.rerun()
    
    # Main upload section
    st.subheader("📁 Upload Documents")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_files = st.file_uploader(
            "Select PDF files",
            type=['pdf'],
            accept_multiple_files=True,
            help="Upload one or more PDF documents"
        )
    
    with col2:
        analysis_type = st.selectbox(
            "Analysis Type",
            options=[
                "content_improvement",
                "full_automation",
                "quality_check"
            ]
        )
    
    # Upload button
    if uploaded_files and st.button("📤 Upload Files", type="primary", use_container_width=True):
        
        with st.spinner(f"Uploading {len(uploaded_files)} files..."):
            # Create batch
            batch_id = f"batch_{uuid.uuid4().hex[:12]}"
            db.create_batch(batch_id, user_email, analysis_type, len(uploaded_files))
            
            # Save each file
            for uploaded_file in uploaded_files:
                # Save file locally
                file_path = os.path.join(UPLOAD_DIR, f"{batch_id}_{uploaded_file.name}")
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.read())
                
                # Create document record
                document_id = f"doc_{uuid.uuid4().hex[:12]}"
                document_data = {
                    'document_id': document_id,
                    'batch_id': batch_id,
                    'filename': uploaded_file.name,
                    'local_path': file_path,
                    'analysis_type': analysis_type,
                    'user_email': user_email
                }
                
                db.add_document(document_data)
            
            st.success(f"✅ {len(uploaded_files)} files uploaded successfully!")
            st.info(f"📋 Batch ID: `{batch_id}`")
            st.info("⏳ Files are queued for processing. The background processor will handle them shortly.")
            
            # Store batch ID in session
            st.session_state.current_batch_id = batch_id
    
    # Show batch results
    st.markdown("---")
    st.subheader("📊 View Results")
    
    # Batch selector
    if 'current_batch_id' in st.session_state:
        batch_id_to_view = st.session_state.current_batch_id
    else:
        batch_id_to_view = st.text_input("Enter Batch ID to view results")
    
    if batch_id_to_view and st.button("🔍 View Batch Results"):
        display_batch_results(batch_id_to_view)


def display_batch_results(batch_id: str):
    """Display results for a batch"""
    
    batch = db.get_batch(batch_id)
    if not batch:
        st.error("❌ Batch not found")
        return
    
    # Batch summary
    st.markdown(f"### Batch: `{batch_id}`")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total", batch['total_documents'])
    with col2:
        st.metric("Completed", batch['completed_documents'])
    with col3:
        st.metric("Status", batch['status'].upper())
    with col4:
        progress = (batch['completed_documents'] / batch['total_documents'] * 100) if batch['total_documents'] > 0 else 0
        st.metric("Progress", f"{progress:.0f}%")
    
    # Document details
    st.markdown("#### 📄 Documents")
    
    documents = db.get_batch_documents(batch_id)
    
    for doc in documents:
        status_icon = {
            'queued': '⏱️',
            'processing': '⏳',
            'completed': '✅',
            'failed': '❌'
        }.get(doc['status'], '❓')
        
        with st.expander(f"{status_icon} {doc['filename']} - {doc['status'].upper()}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.text(f"Document ID: {doc['document_id']}")
                st.text(f"Status: {doc['status']}")
                st.text(f"Created: {doc['created_at']}")
                
                if doc['quality_score']:
                    st.text(f"Quality Score: {doc['quality_score']:.1f}/10")
                
                if doc['status'] == 'completed':
                    st.success("✅ Processing completed")
                    if doc['sharepoint_url']:
                        st.markdown(f"**[📥 Download Improved Document]({doc['sharepoint_url']})**")
                    if doc['report_url']:
                        st.markdown(f"**[📊 View Report]({doc['report_url']})**")
                
                elif doc['status'] == 'failed':
                    st.error("❌ Processing failed")
                    if doc['error_message']:
                        st.error(f"Error: {doc['error_message']}")
                    if doc['report_url']:
                        st.markdown(f"**[📋 View Failure Report]({doc['report_url']})**")
                
                elif doc['status'] == 'processing':
                    st.info("⏳ Currently processing...")
                
                else:
                    st.warning("⏱️ Queued for processing")
            
            with col2:
                if doc['quality_score']:
                    score = doc['quality_score']
                    if score >= 7.0:
                        st.success(f"**{score:.1f}/10** ✅")
                    else:
                        st.error(f"**{score:.1f}/10** ❌")


if __name__ == "__main__":
    main()
