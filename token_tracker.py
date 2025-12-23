import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import json

class TokenTracker:
    """
    Tracks token usage across document analysis workflows and stores in SQLite database.
    """
    
    def __init__(self, db_path: str = "token_usage.db"):
        self.db_path = db_path
        self.current_session_tokens = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0
        }
        self.current_document_name = None
        self.current_workflow_mode = None
        self.session_start_time = None
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main token usage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_name TEXT NOT NULL,
                workflow_mode TEXT NOT NULL,
                analysis_timestamp TIMESTAMP NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                analysis_duration_seconds REAL,
                document_size_chars INTEGER,
                document_pages INTEGER,
                total_images INTEGER,
                status TEXT DEFAULT 'completed',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Agent-level token breakdown table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                call_count INTEGER DEFAULT 1,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES token_usage(id)
            )
        """)
        
        # API call details table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_call_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                model_name TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                call_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES token_usage(id)
            )
        """)
        
        # Cost estimation table (optional - for future cost tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cost_estimation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                model_name TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                estimated_cost_usd REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES token_usage(id)
            )
        """)
        
        conn.commit()
        conn.close()
        
        print(f"✅ Token tracking database initialized at: {self.db_path}")
    
    def start_session(self, document_name: str, workflow_mode: str, 
                      document_size: int = 0, document_pages: int = 0, 
                      total_images: int = 0):
        """Start a new tracking session for a document"""
        self.current_document_name = document_name
        self.current_workflow_mode = workflow_mode
        self.session_start_time = datetime.now()
        
        # Reset counters
        self.current_session_tokens = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'document_size': document_size,
            'document_pages': document_pages,
            'total_images': total_images
        }
        
        print(f"📊 Started token tracking session for: {document_name} ({workflow_mode} mode)")
    
    def track_api_call(self, agent_name: str, response: Any, model_name: str = "gpt-4o-mini"):
        """
        Track tokens from an API response.
        Works with LangChain ChatOpenAI response objects.
        """
        try:
            # Extract token usage from response
            if hasattr(response, 'response_metadata'):
                # LangChain response format
                usage = response.response_metadata.get('token_usage', {})
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', 0)
            elif hasattr(response, 'usage'):
                # Direct OpenAI response format
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens
            else:
                print(f"⚠️ Could not extract token usage from response for {agent_name}")
                return
            
            # Aggregate tokens
            self.current_session_tokens['prompt_tokens'] += prompt_tokens
            self.current_session_tokens['completion_tokens'] += completion_tokens
            self.current_session_tokens['total_tokens'] += total_tokens
            
            print(f"  🔢 {agent_name}: +{total_tokens} tokens (prompt: {prompt_tokens}, completion: {completion_tokens})")
            
        except Exception as e:
            print(f"⚠️ Error tracking tokens for {agent_name}: {e}")
    
    def end_session(self, status: str = "completed", error_message: Optional[str] = None) -> int:
        """
        End tracking session and save to database.
        Returns the session_id.
        """
        if not self.current_document_name or not self.session_start_time:
            print("⚠️ No active session to end")
            return None
        
        analysis_duration = (datetime.now() - self.session_start_time).total_seconds()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert main session record
        cursor.execute("""
            INSERT INTO token_usage 
            (document_name, workflow_mode, analysis_timestamp, prompt_tokens, 
             completion_tokens, total_tokens, analysis_duration_seconds, 
             document_size_chars, document_pages, total_images, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.current_document_name,
            self.current_workflow_mode,
            self.session_start_time,
            self.current_session_tokens['prompt_tokens'],
            self.current_session_tokens['completion_tokens'],
            self.current_session_tokens['total_tokens'],
            analysis_duration,
            self.current_session_tokens.get('document_size', 0),
            self.current_session_tokens.get('document_pages', 0),
            self.current_session_tokens.get('total_images', 0),
            status,
            error_message
        ))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Session ended. Total tokens used: {self.current_session_tokens['total_tokens']}")
        print(f"   Session ID: {session_id}")
        print(f"   Duration: {analysis_duration:.2f} seconds")
        
        # Reset session
        self.current_document_name = None
        self.current_workflow_mode = None
        self.session_start_time = None
        
        return session_id
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get current session summary"""
        return {
            'document_name': self.current_document_name,
            'workflow_mode': self.current_workflow_mode,
            'tokens': self.current_session_tokens.copy(),
            'duration': (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0
        }
    
    def get_total_usage(self) -> Dict[str, Any]:
        """Get total token usage across all documents"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_documents,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                AVG(total_tokens) as avg_tokens_per_doc,
                SUM(analysis_duration_seconds) as total_analysis_time
            FROM token_usage
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            'total_documents': result[0] or 0,
            'total_prompt_tokens': result[1] or 0,
            'total_completion_tokens': result[2] or 0,
            'total_tokens': result[3] or 0,
            'avg_tokens_per_document': round(result[4] or 0, 2),
            'total_analysis_time_seconds': round(result[5] or 0, 2)
        }
    
    def get_recent_sessions(self, limit: int = 10):
        """Get recent analysis sessions"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT *
            FROM token_usage
            ORDER BY analysis_timestamp DESC
            LIMIT ?
        """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_usage_by_workflow(self):
        """Get token usage grouped by workflow mode"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                workflow_mode,
                COUNT(*) as document_count,
                SUM(total_tokens) as total_tokens,
                AVG(total_tokens) as avg_tokens,
                SUM(analysis_duration_seconds) as total_duration
            FROM token_usage
            GROUP BY workflow_mode
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'workflow_mode': row[0],
                'document_count': row[1],
                'total_tokens': row[2],
                'avg_tokens': round(row[3], 2),
                'total_duration_seconds': round(row[4], 2)
            }
            for row in results
        ]
    
    def export_to_csv(self, output_file: str = "token_usage_export.csv"):
        """Export token usage data to CSV"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM token_usage ORDER BY analysis_timestamp DESC")
        rows = cursor.fetchall()
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        
        conn.close()
        
        import csv
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(column_names)
            writer.writerows(rows)
        
        print(f"✅ Exported {len(rows)} records to {output_file}")
        return output_file
