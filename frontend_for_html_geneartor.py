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
            
            # HTML BUTTONS - AFTER TEXTAREA
            st.markdown("**Generate HTML:**")
            col_txt, col_html = st.columns([1, 2])
            
            with col_txt:
                st.download_button(
                    label="📄 TXT", 
                    data=improved_content,
                    file_name=f"{results.get('document_name', 'document')}_automation.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col_html:
                if generate_html_report:
                    if st.button("✨ View as HTML", type="primary", use_container_width=True, key="html_tab5"):
                        with st.spinner("🎨 Generating HTML..."):
                            try:
                                images = results.get('parsed_content', {}).get('images', [])
                                doc_name = results.get('document_name', 'document')
                                html_content = generate_html_report(improved_content, images, doc_name, 'full_automation')
                                
                                st.session_state.generated_html = html_content
                                st.session_state.html_filename = f"KAT_{doc_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                                st.success("✅ HTML generated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
        
        with col2:
            st.markdown("#### 📈 Automation Score")
            st.metric("Feasibility", f"{improved.get('new_automation_feasibility', 0):.1f}/10")
        
        # DOWNLOAD + PREVIEW - BOTTOM
        if st.session_state.generated_html:
            st.markdown("---")
            st.markdown("#### 📥 HTML Document Ready")
            col_dl, col_prev = st.columns([1, 1])
            
            with col_dl:
                st.download_button(
                    label="📥 Download HTML",
                    data=st.session_state.generated_html,
                    file_name=st.session_state.html_filename,
                    mime="text/html",
                    use_container_width=True
                )
            
            with col_prev:
                if st.button("👁️ Preview HTML", use_container_width=True, key="preview_tab5"):
                    st.components.v1.html(st.session_state.generated_html, height=700, scrolling=True)



with tab4:
    if workflow_mode == 'content_improvement':
        st.subheader("✨ AI-Improved Document")
        improved = results.get('improved_document', {})
        
        if improved:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("#### 📝 Enhanced Content")
                with st.expander("📄 View Improved Document", expanded=True):
                    improved_content = improved.get('improved_content', 'No improved content')
                    st.text_area("Improved Content", value=improved_content, height=500, disabled=True, label_visibility="hidden")
                
                # HTML BUTTONS - AFTER TEXTAREA (same column, clean)
                st.markdown("**Generate HTML:**")
                col_txt, col_html = st.columns([1, 2])
                
                with col_txt:
                    st.download_button(
                        label="📄 TXT", 
                        data=improved_content,
                        file_name=f"{results.get('document_name', 'document')}_improved.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                
                with col_html:
                    if generate_html_report:
                        if st.button("✨ View as HTML", type="primary", use_container_width=True):
                            with st.spinner("🎨 Generating HTML..."):
                                try:
                                    images = results.get('parsed_content', {}).get('images', [])
                                    doc_name = results.get('document_name', 'document')
                                    html_content = generate_html_report(improved_content, images, doc_name, 'content_improvement')
                                    
                                    st.session_state.generated_html = html_content
                                    st.session_state.html_filename = f"KAT_{doc_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                                    st.success("✅ HTML generated!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
            
            with col2:
                st.markdown("#### 📈 Quality Improvements")
                st.metric("Quality Increase", f"+{improved.get('quality_score_increase', 0):.1f}")
                st.metric("Clarity", f"{improved.get('new_clarity_score', 0):.1f}/10")
            
            # DOWNLOAD + PREVIEW - BOTTOM OF TAB
            if st.session_state.generated_html:
                st.markdown("---")
                st.markdown("#### 📥 HTML Document Ready")
                col_dl, col_prev = st.columns([1, 1])
                
                with col_dl:
                    st.download_button(
                        label="📥 Download HTML",
                        data=st.session_state.generated_html,
                        file_name=st.session_state.html_filename,
                        mime="text/html",
                        use_container_width=True
                    )
                
                with col_prev:
                    if st.button("👁️ Preview HTML", use_container_width=True):
                        st.components.v1.html(st.session_state.generated_html, height=700, scrolling=True)
