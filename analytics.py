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
st.markdown("Real-time analytics of AI token consumption and cost tracking")

# Token pricing constants
INPUT_TOKEN_COST_PER_1K = 0.0012  # $0.0012 per 1K input tokens
OUTPUT_TOKEN_COST_PER_1K = 0.0050  # $0.0050 per 1K output tokens

DB_PATH = "token_usage.db"

def calculate_cost(prompt_tokens: int, completion_tokens: int) -> dict:
    """Calculate cost based on token usage"""
    input_cost = (prompt_tokens / 1000) * INPUT_TOKEN_COST_PER_1K
    output_cost = (completion_tokens / 1000) * OUTPUT_TOKEN_COST_PER_1K
    total_cost = input_cost + output_cost
    
    return {
        'input_cost': round(input_cost, 6),
        'output_cost': round(output_cost, 6),
        'total_cost': round(total_cost, 6)
    }

def get_db_connection():
    """Get SQLite database connection"""
    return sqlite3.connect(DB_PATH)

def fetch_summary_stats():
    """Fetch summary statistics with cost calculation"""
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
        WHERE status = 'completed'
    """)
    
    overall = cursor.fetchone()
    
    # Calculate costs
    total_prompt = overall[4] or 0
    total_completion = overall[5] or 0
    costs = calculate_cost(total_prompt, total_completion)
    
    # Workflow mode breakdown
    cursor.execute("""
        SELECT 
            workflow_mode,
            COUNT(*) as session_count,
            SUM(total_tokens) as total_tokens,
            SUM(prompt_tokens) as total_prompt_tokens,
            SUM(completion_tokens) as total_completion_tokens,
            AVG(total_tokens) as avg_tokens,
            SUM(analysis_duration_seconds) as total_duration
        FROM token_usage
        WHERE status = 'completed'
        GROUP BY workflow_mode
    """)
    
    workflow_stats = []
    for row in cursor.fetchall():
        mode_costs = calculate_cost(row[3], row[4])
        workflow_stats.append({
            'workflow_mode': row[0],
            'session_count': row[1],
            'total_tokens': row[2],
            'avg_tokens': row[5],
            'total_duration': row[6],
            'total_cost': mode_costs['total_cost'],
            'input_cost': mode_costs['input_cost'],
            'output_cost': mode_costs['output_cost']
        })
    
    conn.close()
    
    return {
        'overall': overall,
        'costs': costs,
        'workflow_stats': workflow_stats
    }

def fetch_all_sessions():
    """Fetch all sessions with cost calculation"""
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
    
    # Calculate cost for each row
    df['input_cost_usd'] = (df['prompt_tokens'] / 1000) * INPUT_TOKEN_COST_PER_1K
    df['output_cost_usd'] = (df['completion_tokens'] / 1000) * OUTPUT_TOKEN_COST_PER_1K
    df['total_cost_usd'] = df['input_cost_usd'] + df['output_cost_usd']
    
    return df

def fetch_agent_breakdown(session_id: int):
    """Fetch agent breakdown with cost calculation"""
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
    
    # Calculate cost for each agent
    df['input_cost_usd'] = (df['prompt_tokens'] / 1000) * INPUT_TOKEN_COST_PER_1K
    df['output_cost_usd'] = (df['completion_tokens'] / 1000) * OUTPUT_TOKEN_COST_PER_1K
    df['total_cost_usd'] = df['input_cost_usd'] + df['output_cost_usd']
    
    return df

# ----------------------
# Refresh Button
# ----------------------

col_refresh, col_export, col_pricing = st.columns([1, 2, 2])

with col_refresh:
    if st.button("🔄 Refresh Data", use_container_width=True, type="primary"):
        st.rerun()

with col_export:
    if st.button("📥 Export All Data to CSV", use_container_width=True):
        df_export = fetch_all_sessions()
        csv_data = df_export.to_csv(index=False)
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_data,
            file_name=f"token_usage_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

with col_pricing:
    with st.expander("💰 Token Pricing Info"):
        st.write(f"**Input Tokens:** ${INPUT_TOKEN_COST_PER_1K:.4f} per 1K tokens")
        st.write(f"**Output Tokens:** ${OUTPUT_TOKEN_COST_PER_1K:.4f} per 1K tokens")
        st.caption("Prices based on GPT-4o-mini Azure OpenAI rates")

st.divider()

# ----------------------
# Summary Statistics with Cost
# ----------------------

st.markdown("## 📈 Overall Statistics")

stats = fetch_summary_stats()
overall = stats['overall']
costs = stats['costs']

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("Total Sessions", f"{overall[0]:,}" if overall[0] else "0")
with col2:
    st.metric("✅ Completed", f"{overall[1]:,}" if overall[1] else "0")
with col3:
    st.metric("Total Tokens", f"{overall[3]:,}" if overall[3] else "0")
with col4:
    st.metric("💰 Total Cost", f"${costs['total_cost']:.4f}")
with col5:
    st.metric("📥 Input Cost", f"${costs['input_cost']:.4f}")
with col6:
    st.metric("📤 Output Cost", f"${costs['output_cost']:.4f}")

# Cost breakdown chart
st.markdown("### 💰 Cost Breakdown")
col_cost1, col_cost2, col_cost3 = st.columns(3)

with col_cost1:
    avg_cost_per_doc = costs['total_cost'] / (overall[1] or 1)
    st.metric(
        "Avg Cost per Document",
        f"${avg_cost_per_doc:.4f}",
        help="Average cost per completed document analysis"
    )

with col_cost2:
    input_percentage = (costs['input_cost'] / costs['total_cost'] * 100) if costs['total_cost'] > 0 else 0
    st.metric(
        "Input Cost %",
        f"{input_percentage:.1f}%",
        help="Percentage of total cost from input tokens"
    )

with col_cost3:
    output_percentage = (costs['output_cost'] / costs['total_cost'] * 100) if costs['total_cost'] > 0 else 0
    st.metric(
        "Output Cost %",
        f"{output_percentage:.1f}%",
        help="Percentage of total cost from output tokens"
    )

st.divider()

# ----------------------
# Workflow Mode Breakdown with Cost
# ----------------------

st.markdown("## 🎯 Token Usage & Cost by Workflow Mode")

if stats['workflow_stats']:
    workflow_data = []
    for row in stats['workflow_stats']:
        workflow_data.append({
            "Workflow Mode": row['workflow_mode'],
            "Sessions": row['session_count'],
            "Total Tokens": f"{int(row['total_tokens']):,}",
            "Avg Tokens": f"{row['avg_tokens']:,.0f}",
            "Total Cost (USD)": f"${row['total_cost']:.4f}",
            "Input Cost (USD)": f"${row['input_cost']:.4f}",
            "Output Cost (USD)": f"${row['output_cost']:.4f}",
            "Avg Cost/Session": f"${row['total_cost']/row['session_count']:.4f}"
        })
    
    df_workflow = pd.DataFrame(workflow_data)
    st.dataframe(df_workflow, use_container_width=True, hide_index=True)
else:
    st.info("No workflow data available yet")

st.divider()

# ----------------------
# All Sessions Table with Cost
# ----------------------

st.markdown("## 📋 All Analysis Sessions")

df_sessions = fetch_all_sessions()

if not df_sessions.empty:
    # Format the dataframe
    df_sessions['analysis_timestamp'] = pd.to_datetime(df_sessions['analysis_timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    df_sessions['total_tokens'] = df_sessions['total_tokens'].apply(lambda x: f"{x:,}")
    df_sessions['prompt_tokens'] = df_sessions['prompt_tokens'].apply(lambda x: f"{x:,}")
    df_sessions['completion_tokens'] = df_sessions['completion_tokens'].apply(lambda x: f"{x:,}")
    df_sessions['total_cost_usd'] = df_sessions['total_cost_usd'].apply(lambda x: f"${x:.4f}")
    df_sessions['input_cost_usd'] = df_sessions['input_cost_usd'].apply(lambda x: f"${x:.6f}")
    df_sessions['output_cost_usd'] = df_sessions['output_cost_usd'].apply(lambda x: f"${x:.6f}")
    df_sessions['analysis_duration_seconds'] = df_sessions['analysis_duration_seconds'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A")
    
    # Rename columns
    df_sessions_display = df_sessions[[
        'id', 'document_name', 'workflow_mode', 'analysis_timestamp',
        'total_tokens', 'total_cost_usd', 'input_cost_usd', 'output_cost_usd',
        'analysis_duration_seconds', 'status'
    ]].copy()
    
    df_sessions_display.columns = [
        "Session ID", "Document Name", "Workflow", "Timestamp",
        "Total Tokens", "Total Cost", "Input Cost", "Output Cost",
        "Duration (s)", "Status"
    ]
    
    st.dataframe(df_sessions_display, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # ----------------------
    # Agent Breakdown with Cost
    # ----------------------
    
    st.markdown("## 🔍 Agent Token & Cost Breakdown by Session")
    
    df_sessions_raw = fetch_all_sessions()
    session_ids = df_sessions_raw['id'].tolist()
    session_names = [f"Session {sid} - {name}" for sid, name in zip(df_sessions_raw['id'], df_sessions_raw['document_name'])]
    
    selected_session_idx = st.selectbox(
        "Select a session:",
        range(len(session_ids)),
        format_func=lambda i: session_names[i]
    )
    
    if selected_session_idx is not None:
        selected_session_id = session_ids[selected_session_idx]
        
        df_agent_breakdown = fetch_agent_breakdown(selected_session_id)
        
        if not df_agent_breakdown.empty:
            st.markdown(f"### 🤖 Agent Breakdown for Session {selected_session_id}")
            
            # Show total cost for session
            total_session_cost = df_agent_breakdown['total_cost_usd'].sum()
            st.info(f"💰 **Total Session Cost:** ${total_session_cost:.6f}")
            
            # Format
            df_agent_breakdown['prompt_tokens'] = df_agent_breakdown['prompt_tokens'].apply(lambda x: f"{x:,}")
            df_agent_breakdown['completion_tokens'] = df_agent_breakdown['completion_tokens'].apply(lambda x: f"{x:,}")
            df_agent_breakdown['total_tokens'] = df_agent_breakdown['total_tokens'].apply(lambda x: f"{x:,}")
            df_agent_breakdown['total_cost_usd'] = df_agent_breakdown['total_cost_usd'].apply(lambda x: f"${x:.6f}")
            df_agent_breakdown['input_cost_usd'] = df_agent_breakdown['input_cost_usd'].apply(lambda x: f"${x:.6f}")
            df_agent_breakdown['output_cost_usd'] = df_agent_breakdown['output_cost_usd'].apply(lambda x: f"${x:.6f}")
            df_agent_breakdown['call_count'] = df_agent_breakdown['call_count'].apply(lambda x: f"{x:,}")
            
            df_agent_breakdown.columns = [
                "Agent Name", "Prompt Tokens", "Completion Tokens", "Total Tokens",
                "API Calls", "Input Cost", "Output Cost", "Total Cost"
            ]
            
            st.dataframe(df_agent_breakdown, use_container_width=True, hide_index=True)
        else:
            st.info(f"No agent breakdown available for Session {selected_session_id}")

else:
    st.info("📭 No analysis sessions found. Process some documents first!")

st.divider()

# Footer
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: gray;'>
    <p>Token Usage & Cost Analytics Dashboard</p>
    <p>💰 Pricing: Input ${INPUT_TOKEN_COST_PER_1K:.4f}/1K | Output ${OUTPUT_TOKEN_COST_PER_1K:.4f}/1K tokens</p>
    <p>Click <strong>Refresh Data</strong> to update with latest results</p>
    </div>
    """,
    unsafe_allow_html=True
)
