#!/usr/bin/env python3
"""
KAT Document Processor Watcher
- Watches database every 30 seconds
- Processes MAX 2 documents in parallel  
- Prevents overlap with file lock
- Graceful shutdown
"""

import time
import logging
import os
import sys
import signal
from pathlib import Path
from datetime import datetime

from processor import DocumentProcessor
from database import DocumentDatabase

# Configuration
LOCK_FILE = Path("/tmp/kat_watcher.lock")
CHECK_INTERVAL = 30  # seconds
MAX_CONCURRENT = 2    # Max parallel documents

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('watcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global state
db = DocumentDatabase()
processor = DocumentProcessor()
shutdown_flag = False

def signal_handler(signum, frame):
    """Graceful shutdown on Ctrl+C"""
    global shutdown_flag
    logger.info("🛑 Shutdown signal received, cleaning up...")
    shutdown_flag = True

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def is_already_running() -> bool:
    """Check if watcher is already running using file lock"""
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            logger.error(f"❌ Watcher already running (PID: {pid}). Exiting.")
            return True
        except (OSError, ValueError):
            logger.warning("🔓 Found stale lock, removing...")
            LOCK_FILE.unlink()
    return False

def acquire_lock() -> bool:
    """Acquire exclusive lock for this watcher instance"""
    try:
        LOCK_FILE.write_text(str(os.getpid()))
        logger.info(f"🔒 Lock acquired (PID: {os.getpid()})")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to acquire lock: {e}")
        return False

def release_lock():
    """Release lock file"""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
            logger.info("🔓 Lock released")
    except Exception as e:
        logger.warning(f"⚠️ Lock cleanup failed: {e}")

def watch_database():
    """Main watcher loop"""
    global shutdown_flag
    
    # 1. CHECK FOR OVERLAP
    if is_already_running():
        sys.exit(1)
    
    if not acquire_lock():
        sys.exit(1)
    
    try:
        logger.info("🚀 Starting KAT Document Watcher")
        logger.info(f"📊 Config: Check every {CHECK_INTERVAL}s, Max {MAX_CONCURRENT} parallel docs")
        
        last_queued_count = 0
        consecutive_no_work = 0
        
        while not shutdown_flag:
            try:
                # 2. CHECK DATABASE FOR PENDING WORK
                stats = db.get_processing_stats()
                queued_count = stats['queued']
                
                logger.info(
                    f"📊 Status: queued={queued_count}, "
                    f"processing={stats['processing']}, "
                    f"completed={stats['completed']}, failed={stats['failed']}"
                )
                
                # 3. PROCESS IF NEW WORK FOUND
                if queued_count > 0:
                    if queued_count != last_queued_count:
                        logger.info(f"📋 New work detected ({queued_count} queued) - processing...")
                        
                        # 4. RUN PROCESSOR (MAX 2 PARALLEL DOCS)
                        processor.run()  # ← Uses ThreadPoolExecutor(max_workers=2)
                        
                        consecutive_no_work = 0
                        last_queued_count = 0  # Reset
                    else:
                        logger.debug("⏳ No new work, but queue exists")
                        consecutive_no_work += 1
                else:
                    consecutive_no_work += 1
                    last_queued_count = 0
                
                # 5. IDLE LOGGING
                if consecutive_no_work % 10 == 0:  # Every 5 minutes
                    logger.info(f"😴 Idle for {consecutive_no_work * CHECK_INTERVAL}s - watching...")
                
                # 6. SLEEP
                for i in range(CHECK_INTERVAL):
                    if shutdown_flag:
                        break
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Watch loop error: {e}")
                time.sleep(CHECK_INTERVAL)
        
        logger.info("✅ Watcher stopped gracefully")
        
    finally:
        # 7. ALWAYS CLEANUP LOCK
        release_lock()

if __name__ == "__main__":
    watch_database()
