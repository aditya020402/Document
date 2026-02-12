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

def validate_and_format_email(email: str) -> str:
    """Force UBS.com domain"""
    email = email.strip().lower()
    if '@' in email:
        username, domain = email.split('@', 1)
        if domain != 'ubs.com':
            st.error("❌ Only UBS.com email addresses allowed!")
            st.stop()
        return f"{username}@{domain}"
    return f"{email}@ubs.com"

def get_user_batches(user_email: str, limit: int = 10) -> list:
    """Get recent batches for user"""
    return db.get_user_batches(user_email, limit)

def main():
    st.set_page_config(page_title="KAT Bulk Upload", page_icon="📤", layout="wide")
    
    st.title("📤 KAT - UBS Document Upload")
    st.markdown("**UBS.com** employees only - Upload & track document processing")
    
    # Sidebar - UBS Email
    with st.sidebar:
        st.header("👤 UBS Employee")
        
        email_input = st.text_input(
            "🔍 UBS Email",
            placeholder="aditya.sharma or aditya.sharma@ubs.com",
            help="Search your batches or upload new ones"
        )
        
        if email_input:
            formatted_email = validate_and_format_email(email_input)
            if '@' not in email_input:
                st.info(f"✅ Auto-completed: **{formatted_email}**")
            st.session_state.user_email = formatted_email
        
        if 'user_email' in st.session_state:
            st.success(f"👤 **{st.session_state.user_email}**")
        else:
            st.warning("⚠️ Enter UBS email to continue")
        
        st.markdown("---")
        st.header("📊 Queue Status")
        stats = db.get_processing_stats()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("⏳ Queued", stats['queued'])
        col2.metric("🔄 Processing", stats['processing'])
        col3.metric("✅ Completed", stats['completed'])
        col4.metric("❌ Failed", stats['failed'])
        
        if st.button("🔄 Refresh"):
            st.rerun()
    
    # Require UBS email
    try:
        user_email = st.session_state.user_email
    except AttributeError:
        st.error("🚫 **Enter your UBS.com email first!**")
        st.stop()
    
    # Main interface - TABS for better UX
    tab1, tab2 = st.tabs(["📤 Upload New", "📊 My Batches"])
    
    with tab1:
        st.subheader("📁 Upload Documents")
        st.info(f"👤 **{user_email}**")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_files = st.file_uploader(
                "Select PDFs",
                type=['pdf'],
                accept_multiple_files=True
            )
        with col2:
            analysis_type = st.selectbox(
                "Analysis",
                ["content_improvement", "full_automation", "quality_check"]
            )
        
        if uploaded_files and st.button("🚀 Upload & Queue", type="primary"):
            with st.spinner(f"📤 Uploading {len(uploaded_files)} files..."):
                batch_id = f"ubs_{uuid.uuid4().hex[:12]}"
                db.create_batch(batch_id, user_email, analysis_type, len(uploaded_files))
                
                success_count = 0
                for uploaded_file in uploaded_files:
                    try:
                        file_path = os.path.join(UPLOAD_DIR, f"{batch_id}_{uploaded_file.name}")
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.read())
                        
                        document_id = f"doc_{uuid.uuid4().hex[:12]}"
                        document_data = {
                            'document_id': document_id,
                            'batch_id': batch_id,
                            'filename': uploaded_file.name,
                            'local_path': file_path,
                            'analysis_type': analysis_type,
                            'user_email': user_email
                        }
                        
                        if db.add_document(document_data):
                            success_count += 1
                            
                    except Exception as e:
                        st.error(f"❌ {uploaded_file.name}: {e}")
                
                st.success(f"✅ **{success_count}/{len(uploaded_files)}** queued!")
                st.info(f"📋 **Batch ID:** `{batch_id}`")
                st.balloons()
                st.rerun()
    
    with tab2:
        st.subheader("📊 My Processing History")
        st.info(f"🔍 Showing recent batches for **{user_email}**")
        
        # Email-based search (automatic)
        user_batches = get_user_batches(user_email, limit=20)
        
        if not user_batches:
            st.info("📭 No batches found. Upload documents to get started!")
            st.stop()
        
        # Batch list
        for batch in user_batches:
            with st.expander(f"📦 **{batch['batch_id']}** - {batch['status'].upper()} ({batch['completed_documents']}/{batch['total_documents']})", expanded=False):
                
                col1, col2, col3 = st.columns([1, 2, 2])
                with col1:
                    st.metric("Progress", f"{batch['completed_documents']}/{batch['total_documents']}")
                with col2:
                    st.markdown(f"**Created:** {batch['created_at']}")
                    st.markdown(f"**Type:** {batch['analysis_type']}")
                with col3:
                    st.markdown(f"**Status:** {batch['status']}")
                    st.markdown(f"**Updated:** {batch['updated_at']}")
                
                # Show documents in this batch
                documents = db.get_batch_documents(batch['batch_id'])
                for doc in documents:
                    status_emoji = {
                        'queued': '⏳ Queued',
                        'processing': '🔄 Processing', 
                        'completed': '✅ Complete',
                        'failed': '❌ Failed'
                    }.get(doc['status'], '❓ Unknown')
                    
                    doc_col1, doc_col2 = st.columns([3, 1])
                    with doc_col1:
                        st.markdown(f"**{doc['filename']}** - {status_emoji}")
                        if doc['quality_score']:
                            color = "🟢" if doc['quality_score'] >= 7.0 else "🔴"
                            st.markdown(f"{color} **Score: {doc['quality_score']:.1f}/10**")
                        
                        if doc['sharepoint_url']:
                            st.markdown(f"[📥 Download]({doc['sharepoint_url']})")
                        if doc['report_url']:
                            st.markdown(f"[📊 Report]({doc['report_url']})")
                    
                    with doc_col2:
                        if doc['status'] in ['completed', 'failed']:
                            if doc['quality_score']:
                                score = doc['quality_score']
                                if score >= 7.0:
                                    st.success(f"**PASSED**")
                                else:
                                    st.error(f"**FAILED**")
                            else:
                                st.info("**N/A**")
    
    # Footer
    st.markdown("---")
    st.markdown("*KAT - UBS Document Automation System*")

if __name__ == "__main__":
    main()
