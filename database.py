import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
import threading

db_lock = threading.Lock()

class DocumentDatabase:
    """SQLite database for document processing"""
    
    def __init__(self, db_path: str = "document_processing.db"):
        self.db_path = db_path
        self._init_database()
    
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        """Initialize database schema"""
        with db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Batch table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batches (
                    batch_id TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    analysis_type TEXT NOT NULL,
                    total_documents INTEGER DEFAULT 0,
                    completed_documents INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    analysis_type TEXT NOT NULL,
                    user_email TEXT NOT NULL,
                    status TEXT DEFAULT 'queued',
                    quality_score REAL,
                    processing_started_at TIMESTAMP,
                    processing_completed_at TIMESTAMP,
                    sharepoint_url TEXT,
                    report_url TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
                )
            """)
            
            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON documents(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch ON documents(batch_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created ON documents(created_at)")
            
            conn.commit()
            conn.close()
    
    # ========================================
    # BATCH OPERATIONS
    # ========================================
    
    def create_batch(self, batch_id: str, user_email: str, analysis_type: str, total_docs: int) -> bool:
        with db_lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO batches (batch_id, user_email, analysis_type, total_documents)
                    VALUES (?, ?, ?, ?)
                """, (batch_id, user_email, analysis_type, total_docs))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error creating batch: {e}")
                return False
    
    def get_batch(self, batch_id: str) -> Optional[Dict]:
        with db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM batches WHERE batch_id = ?", (batch_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def update_batch_progress(self, batch_id: str):
        with db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) as completed 
                FROM documents 
                WHERE batch_id = ? AND status IN ('completed', 'failed')
            """, (batch_id,))
            completed = cursor.fetchone()['completed']
            
            cursor.execute("""
                UPDATE batches 
                SET completed_documents = ?,
                    status = CASE 
                        WHEN ? >= total_documents THEN 'completed'
                        ELSE 'processing'
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE batch_id = ?
            """, (completed, completed, batch_id))
            
            conn.commit()
            conn.close()
    
    # ========================================
    # DOCUMENT OPERATIONS
    # ========================================
    
    def add_document(self, document_data: Dict[str, Any]) -> bool:
        with db_lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO documents 
                    (document_id, batch_id, filename, local_path, analysis_type, user_email)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    document_data['document_id'],
                    document_data['batch_id'],
                    document_data['filename'],
                    document_data['local_path'],
                    document_data['analysis_type'],
                    document_data['user_email']
                ))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error adding document: {e}")
                return False
    
    def get_pending_documents(self, limit: int = 2) -> List[Dict]:
        """Get next pending documents (FIFO) - limited by max_workers"""
        with db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM documents 
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    def mark_document_processing(self, document_id: str) -> bool:
        """Mark document as being processed"""
        with db_lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE documents 
                    SET status = 'processing',
                        processing_started_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE document_id = ?
                """, (document_id,))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error marking document: {e}")
                return False
    
    def update_document_status(self, document_id: str, status: str, **kwargs):
        with db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            update_fields = ['status = ?', 'updated_at = CURRENT_TIMESTAMP']
            values = [status]
            
            if status in ('completed', 'failed'):
                update_fields.append('processing_completed_at = CURRENT_TIMESTAMP')
            
            if 'quality_score' in kwargs:
                update_fields.append('quality_score = ?')
                values.append(kwargs['quality_score'])
            if 'sharepoint_url' in kwargs:
                update_fields.append('sharepoint_url = ?')
                values.append(kwargs['sharepoint_url'])
            if 'report_url' in kwargs:
                update_fields.append('report_url = ?')
                values.append(kwargs['report_url'])
            if 'error_message' in kwargs:
                update_fields.append('error_message = ?')
                values.append(kwargs['error_message'])
            
            values.append(document_id)
            
            query = f"UPDATE documents SET {', '.join(update_fields)} WHERE document_id = ?"
            cursor.execute(query, values)
            conn.commit()
            conn.close()
    
    def get_document(self, document_id: str) -> Optional[Dict]:
        with db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def get_batch_documents(self, batch_id: str) -> List[Dict]:
        with db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE batch_id = ? ORDER BY created_at", (batch_id,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    def get_processing_stats(self) -> Dict[str, int]:
        with db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            stats = {}
            cursor.execute("SELECT COUNT(*) as count FROM documents WHERE status = 'queued'")
            stats['queued'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM documents WHERE status = 'processing'")
            stats['processing'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM documents WHERE status = 'completed'")
            stats['completed'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM documents WHERE status = 'failed'")
            stats['failed'] = cursor.fetchone()['count']
            
            conn.close()
            return stats


    def get_user_batches(self, user_email: str, limit: int = 10) -> List[Dict]:
        """Get recent batches for specific user"""
        with db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT b.* 
                FROM batches b
                WHERE b.user_email = ?
                ORDER BY b.created_at DESC
                LIMIT ?
            """, (user_email, limit))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
