with tab4:
    if workflow_mode == 'content_improvement':
        st.subheader("✨ AI-Improved Document")
        results = st.session_state.get('results')
        
        if results and results.get('improved_document'):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("#### 📝 Enhanced Content")
                with st.expander("📄 View Improved Document", expanded=True):
                    improved_content = results['improved_document'].get('improved_content', 'No content')
                    st.text_area("Improved Content", value=improved_content, height=500, disabled=True, label_visibility="hidden")
                
                # ✅ ONLY TXT DOWNLOAD - No HTML generate button
                st.markdown("**💾 Export Options:**")
                st.download_button(
                    label="📄 TXT", 
                    data=improved_content,
                    file_name=f"{results.get('document_name', 'document')}_improved.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col2:
                st.markdown("#### 📈 Quality Improvements")
                improved = results['improved_document']
                st.metric("Quality Increase", f"+{improved.get('quality_score_increase', 0):.1f}")
                st.metric("Clarity", f"{improved.get('new_clarity_score', 0):.1f}/10")
                st.metric("Completeness", f"{improved.get('new_completeness_score', 0):.1f}/10")
            
            # ✅ HTML FROM BACKEND - Auto-appears
            if results.get('html_report'):
                st.markdown("---")
                st.markdown("#### 📥 HTML Document Ready")
                col_dl, col_prev = st.columns([1, 1])
                
                with col_dl:
                    st.download_button(
                        label="📥 Download HTML",
                        data=results['html_report']['content'],
                        file_name=results['html_report']['filename'],
                        mime="text/html",
                        use_container_width=True
                    )
                
                with col_prev:
                    if st.button("👁️ Preview HTML", use_container_width=True, key="preview_tab4"):
                        st.markdown("### 📄 Live HTML Preview")
                        st.components.v1.html(results['html_report']['content'], height=700, scrolling=True)
            else:
                st.info("ℹ️ HTML will appear automatically after processing")
