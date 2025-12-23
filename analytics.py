import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path

st.set_page_config(
    page_title="Token Usage Analytics",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Token Usage Analytics Dashboard")
st.markdown("Real-time analytics of AI token consumption across all document analyses")

# Database path
DB_PATH = "token_usage.db"

def get_db_connection():
    """Get SQLite database connection"""
    return sqlite3.connect(DB_PATH)

def fetch_all_sessions():
    """Fetch all token usage sessions"""
    conn = get_db_connection()
    query = """
        SELECT 
            id,
            document_name,
            workflow_mode,
            analysis_timestamp,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            analysis_duration_seconds,
            document_size_chars,
            document_pages,
            total_images,
            status,
            error_message
        FROM token_usage
        ORDER BY analysis_timestamp DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def fetch_agent_breakdown(session_id: int):
    """Fetch agent-level token breakdown for a session"""
    conn = get_db_connection()
    query = """
        SELECT 
            agent_name,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            call_count
        FROM agent_token_usage
        WHERE session_id = ?
        ORDER BY total_tokens DESC
    """
    df = pd.read_sql_query(query, conn, params=(session_id,))
    conn.close()
    return df

def fetch_summary_stats():
    """Fetch summary statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Overall stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_sessions,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_sessions,
            SUM(total_tokens) as total_tokens,
            SUM(prompt_tokens) as total_prompt_tokens,
            SUM(completion_tokens) as total_completion_tokens,
            AVG(total_tokens) as avg_tokens_per_session,
            SUM(analysis_duration_seconds) as total_analysis_time,
            AVG(analysis_duration_seconds) as avg_analysis_time
        FROM token_usage
    """)
    
    overall = cursor.fetchone()
    
    # Workflow mode breakdown
    cursor.execute("""
        SELECT 
            workflow_mode,
            COUNT(*) as session_count,
            SUM(total_tokens) as total_tokens,
            AVG(total_tokens) as avg_tokens,
            SUM(analysis_duration_seconds) as total_duration
        FROM token_usage
        WHERE status = 'completed'
        GROUP BY workflow_mode
    """)
    
    workflow_stats = cursor.fetchall()
    
    conn.close()
    
    return {
        'overall': overall,
        'workflow_stats': workflow_stats
    }

def fetch_top_agents():
    """Fetch top agents by token usage across all sessions"""
    conn = get_db_connection()
    query = """
        SELECT 
            agent_name,
            SUM(total_tokens) as total_tokens,
            SUM(prompt_tokens) as total_prompt_tokens,
            SUM(completion_tokens) as total_completion_tokens,
            SUM(call_count) as total_calls,
            AVG(total_tokens) as avg_tokens_per_call
        FROM agent_token_usage
        GROUP BY agent_name
        ORDER BY total_tokens DESC
        LIMIT 10
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ----------------------
# Refresh Button
# ----------------------

col_refresh, col_export = st.columns([1, 5])

with col_refresh:
    if st.button("🔄 Refresh Data", use_container_width=True, type="primary"):
        st.rerun()

with col_export:
    if st.button("📥 Export All Data to CSV", use_container_width=True):
        conn = get_db_connection()
        df_export = pd.read_sql_query("SELECT * FROM token_usage ORDER BY analysis_timestamp DESC", conn)
        conn.close()
        
        csv_data = df_export.to_csv(index=False)
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_data,
            file_name=f"token_usage_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

st.divider()

# ----------------------
# Summary Statistics
# ----------------------

st.markdown("## 📈 Overall Statistics")

stats = fetch_summary_stats()
overall = stats['overall']

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Sessions", f"{overall[0]:,}" if overall[0] else "0")
with col2:
    st.metric("✅ Completed", f"{overall[1]:,}" if overall[1] else "0")
with col3:
    st.metric("❌ Failed", f"{overall[2]:,}" if overall[2] else "0")
with col4:
    st.metric("Total Tokens Used", f"{overall[3]:,}" if overall[3] else "0")
with col5:
    st.metric("Avg Tokens/Session", f"{overall[6]:,.0f}" if overall[6] else "0")

st.divider()

# ----------------------
# Workflow Mode Breakdown
# ----------------------

st.markdown("## 🎯 Token Usage by Workflow Mode")

if stats['workflow_stats']:
    workflow_data = []
    for row in stats['workflow_stats']:
        workflow_data.append({
            "Workflow Mode": row[0],
            "Sessions": row[1],
            "Total Tokens": f"{row[2]:,}",
            "Avg Tokens": f"{row[3]:,.0f}",
            "Total Duration (s)": f"{row[4]:,.1f}"
        })
    
    df_workflow = pd.DataFrame(workflow_data)
    st.dataframe(df_workflow, use_container_width=True, hide_index=True)
else:
    st.info("No workflow data available yet")

st.divider()

# ----------------------
# Top Agents by Token Usage
# ----------------------

st.markdown("## 🤖 Top Agents by Token Consumption")

df_agents = fetch_top_agents()

if not df_agents.empty:
    df_agents['total_tokens'] = df_agents['total_tokens'].apply(lambda x: f"{x:,}")
    df_agents['total_prompt_tokens'] = df_agents['total_prompt_tokens'].apply(lambda x: f"{x:,}")
    df_agents['total_completion_tokens'] = df_agents['total_completion_tokens'].apply(lambda x: f"{x:,}")
    df_agents['total_calls'] = df_agents['total_calls'].apply(lambda x: f"{x:,}")
    df_agents['avg_tokens_per_call'] = df_agents['avg_tokens_per_call'].apply(lambda x: f"{x:,.1f}")
    
    df_agents.columns = ["Agent Name", "Total Tokens", "Prompt Tokens", "Completion Tokens", "Total Calls", "Avg Tokens/Call"]
    
    st.dataframe(df_agents, use_container_width=True, hide_index=True)
else:
    st.info("No agent data available yet")

st.divider()

# ----------------------
# All Sessions Table
# ----------------------

st.markdown("## 📋 All Analysis Sessions")

df_sessions = fetch_all_sessions()

if not df_sessions.empty:
    # Format the dataframe
    df_sessions['analysis_timestamp'] = pd.to_datetime(df_sessions['analysis_timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    df_sessions['total_tokens'] = df_sessions['total_tokens'].apply(lambda x: f"{x:,}")
    df_sessions['prompt_tokens'] = df_sessions['prompt_tokens'].apply(lambda x: f"{x:,}")
    df_sessions['completion_tokens'] = df_sessions['completion_tokens'].apply(lambda x: f"{x:,}")
    df_sessions['analysis_duration_seconds'] = df_sessions['analysis_duration_seconds'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A")
    df_sessions['document_size_chars'] = df_sessions['document_size_chars'].apply(lambda x: f"{x:,}" if pd.notnull(x) else "0")
    
    # Rename columns for display
    df_sessions.columns = [
        "Session ID", "Document Name", "Workflow Mode", "Analysis Time", 
        "Prompt Tokens", "Completion Tokens", "Total Tokens", 
        "Duration (s)", "Doc Size (chars)", "Pages", "Images", "Status", "Error"
    ]
    
    # Show dataframe with selection
    st.dataframe(
        df_sessions,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn(
                "Status",
                help="Session status: completed or failed"
            ),
            "Error": st.column_config.TextColumn(
                "Error Message",
                help="Error message if failed"
            )
        }
    )
    
    st.divider()
    
    # ----------------------
    # Agent Breakdown for Selected Session
    # ----------------------
    
    st.markdown("## 🔍 Agent Breakdown by Session")
    
    # Get original df for session IDs
    df_sessions_raw = fetch_all_sessions()
    session_ids = df_sessions_raw['id'].tolist()
    session_names = [f"Session {sid} - {name}" for sid, name in zip(df_sessions_raw['id'], df_sessions_raw['document_name'])]
    
    selected_session_idx = st.selectbox(
        "Select a session to view agent breakdown:",
        range(len(session_ids)),
        format_func=lambda i: session_names[i]
    )
    
    if selected_session_idx is not None:
        selected_session_id = session_ids[selected_session_idx]
        
        df_agent_breakdown = fetch_agent_breakdown(selected_session_id)
        
        if not df_agent_breakdown.empty:
            st.markdown(f"### 🤖 Agent Token Breakdown for Session {selected_session_id}")
            
            # Format
            df_agent_breakdown['prompt_tokens'] = df_agent_breakdown['prompt_tokens'].apply(lambda x: f"{x:,}")
            df_agent_breakdown['completion_tokens'] = df_agent_breakdown['completion_tokens'].apply(lambda x: f"{x:,}")
            df_agent_breakdown['total_tokens'] = df_agent_breakdown['total_tokens'].apply(lambda x: f"{x:,}")
            df_agent_breakdown['call_count'] = df_agent_breakdown['call_count'].apply(lambda x: f"{x:,}")
            
            df_agent_breakdown.columns = ["Agent Name", "Prompt Tokens", "Completion Tokens", "Total Tokens", "API Calls"]
            
            st.dataframe(df_agent_breakdown, use_container_width=True, hide_index=True)
        else:
            st.info(f"No agent breakdown available for Session {selected_session_id}")

else:
    st.info("📭 No analysis sessions found. Process some documents first!")

st.divider()

# ----------------------
# Footer
# ----------------------

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
    <p>Token Usage Analytics Dashboard | Data stored in <code>token_usage.db</code></p>
    <p>Click <strong>Refresh Data</strong> to update with latest analysis results</p>
    </div>
    """,
    unsafe_allow_html=True
)
