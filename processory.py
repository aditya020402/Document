import asyncio
import logging
from datetime import datetime
from pathlib import Path
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

from database import DocumentDatabase
from msgraph_sharepoint_service import MSGraphSharePointService
from backend_v4 import DocumentWorkflow  # Your existing backend

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
QUALITY_THRESHOLD = 7.0
MAX_WORKERS = 2  # Process 2 documents at a time

# Initialize services
db = DocumentDatabase()

SHAREPOINT_CONFIG = {
    'site_url': os.getenv('SHAREPOINT_SITE_URL'),
    'client_id': os.getenv('SHAREPOINT_CLIENT_ID'),
    'client_secret': os.getenv('SHAREPOINT_CLIENT_SECRET'),
    'tenant_id': os.getenv('SHAREPOINT_TENANT_ID')
}


class DocumentProcessor:
    """Background processor for documents"""
    
    def __init__(self):
        self.sp_service = None
        self.workflow = DocumentWorkflow()
    
    def _init_sharepoint(self):
        """Lazy initialize SharePoint (only when needed)"""
        if self.sp_service is None:
            self.sp_service = MSGraphSharePointService(SHAREPOINT_CONFIG)
    
    def run(self):
        """Main processing loop - run this via cron"""
        logger.info("=" * 60)
        logger.info("🚀 Starting document processing cycle")
        logger.info("=" * 60)
        
        # Get pending documents
        pending_docs = db.get_pending_documents(limit=MAX_WORKERS)
        
        if not pending_docs:
            logger.info("✅ No pending documents. Exiting.")
            return
        
        logger.info(f"📋 Found {len(pending_docs)} pending documents")
        
        # Process documents in parallel (max 2 threads)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for doc in pending_docs:
                # Mark as processing
                db.mark_document_processing(doc['document_id'])
                
                # Submit to thread pool
                future = executor.submit(self.process_document, doc)
                futures.append(future)
            
            # Wait for all to complete
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"❌ Thread execution error: {e}")
        
        logger.info("=" * 60)
        logger.info("✅ Processing cycle complete")
        logger.info("=" * 60)
    
    def process_document(self, doc: Dict[str, Any]):
        """Process a single document (runs in thread)"""
        document_id = doc['document_id']
        filename = doc['filename']
        
        try:
            logger.info(f"📄 Processing: {filename} (ID: {document_id})")
            
            # Run document through workflow
            result = asyncio.run(self._process_async(doc))
            
            if not result['success']:
                # Processing error
                db.update_document_status(
                    document_id,
                    'failed',
                    error_message=result.get('error', 'Unknown error')
                )
                logger.error(f"❌ {filename}: Processing failed - {result.get('error')}")
                return
            
            # Get quality score
            quality_score = result.get('quality_score', 0)
            
            # Check threshold
            if quality_score >= QUALITY_THRESHOLD:
                # APPROVED - Upload to SharePoint
                self._init_sharepoint()
                upload_result = self._upload_approved(doc, result)
                
                db.update_document_status(
                    document_id,
                    'completed',
                    quality_score=quality_score,
                    sharepoint_url=upload_result.get('content_url', ''),
                    report_url=upload_result.get('html_url', '')
                )
                
                logger.info(f"✅ {filename}: APPROVED (score: {quality_score:.1f}) - Uploaded to SharePoint")
            
            else:
                # REJECTED - Generate failure report
                self._init_sharepoint()
                report_url = self._upload_failure_report(doc, result)
                
                db.update_document_status(
                    document_id,
                    'failed',
                    quality_score=quality_score,
                    report_url=report_url,
                    error_message=f"Quality score {quality_score:.1f} below threshold {QUALITY_THRESHOLD}"
                )
                
                logger.warning(f"⚠️ {filename}: REJECTED (score: {quality_score:.1f})")
            
            # Update batch progress
            db.update_batch_progress(doc['batch_id'])
            
        except Exception as e:
            logger.error(f"❌ {filename}: Unexpected error - {e}")
            db.update_document_status(
                document_id,
                'failed',
                error_message=str(e)
            )
    
    async def _process_async(self, doc: Dict) -> Dict[str, Any]:
        """Run document through workflow"""
        try:
            # Map analysis type to workflow mode
            workflow_mode_map = {
                'content_improvement': 'content_improvement',
                'full_automation': 'full_automation',
                'quality_check': 'content_improvement'
            }
            
            workflow_mode = workflow_mode_map.get(doc['analysis_type'], 'content_improvement')
            
            initial_state = {
                'pdf_path': doc['local_path'],
                'workflow_mode': workflow_mode,
                'messages': [],
                'current_step': 'start'
            }
            
            final_state = await self.workflow.run_workflow(initial_state)
            
            # Extract quality score
            quality_scores = final_state.get('automation_analysis', {}).get('quality_scores', {})
            overall_score = quality_scores.get('overall_score', 0.0)
            
            return {
                'success': True,
                'quality_score': overall_score,
                'workflow_state': final_state
            }
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _upload_approved(self, doc: Dict, result: Dict) -> Dict[str, str]:
        """Upload approved document to SharePoint"""
        try:
            workflow_state = result['workflow_state']
            
            # Get content
            improved_content = workflow_state.get('improved_document', {}).get('improved_content', '')
            html_report = workflow_state.get('generated_html', {})
            
            # Create temp files
            temp_dir = tempfile.mkdtemp()
            
            # HTML file
            html_path = os.path.join(temp_dir, html_report.get('filename', 'report.html'))
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_report.get('content', ''))
            
            # Improved content
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            txt_filename = f"KAT_Improved_{Path(doc['filename']).stem}_{timestamp}.txt"
            txt_path = os.path.join(temp_dir, txt_filename)
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(improved_content)
            
            # Upload
            html_upload = self.sp_service.upload_file_to_folder(html_path, 'KAT_Processed/Approved/Reports')
            txt_upload = self.sp_service.upload_file_to_folder(txt_path, 'KAT_Processed/Approved/Content')
            
            # Cleanup
            os.remove(html_path)
            os.remove(txt_path)
            os.rmdir(temp_dir)
            
            return {
                'html_url': html_upload.get('sharepoint_url', ''),
                'content_url': txt_upload.get('sharepoint_url', '')
            }
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return {'html_url': '', 'content_url': ''}
    
    def _upload_failure_report(self, doc: Dict, result: Dict) -> str:
        """Upload failure report to SharePoint"""
        try:
            quality_score = result.get('quality_score', 0)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            report_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Processing Failed - {doc['filename']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%); color: white; padding: 30px; border-radius: 5px; margin: -30px -30px 30px -30px; }}
        .score {{ font-size: 72px; font-weight: bold; color: #ff4444; text-align: center; margin: 30px 0; }}
        .threshold {{ font-size: 24px; color: #666; text-align: center; }}
        .details {{ background: #f9f9f9; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .recommendations {{ background: #fff3cd; padding: 20px; border-radius: 5px; border-left: 4px solid #ffc107; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>❌ Document Processing Failed</h1>
            <p>Quality threshold not met</p>
        </div>
        
        <div class="score">{quality_score:.1f}/10</div>
        <div class="threshold">Threshold Required: {QUALITY_THRESHOLD}/10</div>
        
        <div class="details">
            <h2>Document Details</h2>
            <p><strong>Filename:</strong> {doc['filename']}</p>
            <p><strong>User:</strong> {doc['user_email']}</p>
            <p><strong>Analysis Type:</strong> {doc['analysis_type']}</p>
            <p><strong>Processed:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Status:</strong> <span style="color: #ff4444; font-weight: bold;">REJECTED</span></p>
        </div>
        
        <div class="recommendations">
            <h3>💡 Recommendations</h3>
            <ul>
                <li>Review document content quality and completeness</li>
                <li>Check for clarity, structure, and formatting</li>
                <li>Ensure all required sections are present</li>
                <li>Verify technical accuracy and consistency</li>
                <li>Resubmit after making improvements</li>
            </ul>
        </div>
    </div>
</body>
</html>
            """
            
            # Save to temp file
            temp_dir = tempfile.mkdtemp()
            report_filename = f"FAILED_{Path(doc['filename']).stem}_{timestamp}.html"
            report_path = os.path.join(temp_dir, report_filename)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_html)
            
            # Upload
            upload_result = self.sp_service.upload_file_to_folder(report_path, 'KAT_Processed/Failed')
            
            # Cleanup
            os.remove(report_path)
            os.rmdir(temp_dir)
            
            return upload_result.get('sharepoint_url', '')
            
        except Exception as e:
            logger.error(f"Failure report upload error: {e}")
            return ''


if __name__ == "__main__":
    processor = DocumentProcessor()
    processor.run()
