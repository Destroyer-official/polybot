"""
Automatic Log Management System.

Handles:
- Daily log rotation with 30-day retention
- Automatic compression of old logs
- Disk space monitoring (<10% triggers cleanup)
- Automatic cleanup of old data

Requirements: 11.5, 11.12
"""

import asyncio
import gzip
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class LogManager:
    """
    Manages automatic log rotation, compression, and cleanup.
    
    Features:
    - Daily log rotation (keep 30 days)
    - Automatic compression of logs older than 1 day
    - Disk space monitoring (<10% triggers cleanup)
    - Automatic cleanup of old data
    """
    
    def __init__(
        self,
        log_dir: str = "logs",
        retention_days: int = 30,
        compression_age_days: int = 1,
        disk_space_threshold: float = 0.10,  # 10%
        check_interval_seconds: int = 3600,  # 1 hour
    ):
        """
        Initialize log manager.
        
        Args:
            log_dir: Directory containing log files
            retention_days: Number of days to keep logs (default: 30)
            compression_age_days: Age in days before compressing logs (default: 1)
            disk_space_threshold: Minimum free disk space percentage (default: 0.10 = 10%)
            check_interval_seconds: How often to check logs and disk space (default: 3600 = 1 hour)
        """
        self.log_dir = Path(log_dir)
        self.retention_days = retention_days
        self.compression_age_days = compression_age_days
        self.disk_space_threshold = disk_space_threshold
        self.check_interval_seconds = check_interval_seconds
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"LogManager initialized: dir={log_dir}, retention={retention_days}d, "
                   f"compression_age={compression_age_days}d, disk_threshold={disk_space_threshold*100:.1f}%")
    
    async def start(self):
        """Start the automatic log management loop."""
        logger.info("Starting automatic log management...")
        
        while True:
            try:
                # Perform log management tasks
                await self.rotate_logs()
                await self.compress_old_logs()
                await self.cleanup_old_logs()
                await self.check_disk_space()
                
                # Wait before next check
                await asyncio.sleep(self.check_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in log management loop: {e}", exc_info=True)
                # Continue running even if there's an error
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def rotate_logs(self):
        """
        Rotate log files daily.
        
        Renames current log files with date suffix (e.g., bot.log -> bot.log.2024-01-15)
        """
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Find all .log files (not already rotated)
            log_files = [f for f in self.log_dir.glob("*.log") if not f.name.endswith(".gz")]
            
            for log_file in log_files:
                # Check if file was modified today
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime.date() < datetime.now().date():
                    # File is from a previous day, rotate it
                    rotated_name = f"{log_file.name}.{current_date}"
                    rotated_path = self.log_dir / rotated_name
                    
                    # Avoid overwriting if already exists
                    if not rotated_path.exists():
                        log_file.rename(rotated_path)
                        logger.info(f"Rotated log: {log_file.name} -> {rotated_name}")
            
        except Exception as e:
            logger.error(f"Error rotating logs: {e}", exc_info=True)
    
    async def compress_old_logs(self):
        """
        Compress log files older than compression_age_days.
        
        Compresses .log files to .log.gz to save disk space.
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.compression_age_days)
            
            # Find all rotated log files (not compressed)
            log_files = [f for f in self.log_dir.glob("*.log.*") if not f.name.endswith(".gz")]
            
            for log_file in log_files:
                # Check file age
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_date:
                    # Compress the file
                    compressed_path = Path(str(log_file) + ".gz")
                    
                    if not compressed_path.exists():
                        await self._compress_file(log_file, compressed_path)
                        logger.info(f"Compressed log: {log_file.name} -> {compressed_path.name}")
                        
                        # Remove original file after successful compression
                        log_file.unlink()
            
        except Exception as e:
            logger.error(f"Error compressing logs: {e}", exc_info=True)
    
    async def _compress_file(self, source: Path, destination: Path):
        """
        Compress a file using gzip.
        
        Args:
            source: Source file path
            destination: Destination compressed file path
        """
        with open(source, 'rb') as f_in:
            with gzip.open(destination, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    async def cleanup_old_logs(self):
        """
        Delete log files older than retention_days.
        
        Removes both compressed and uncompressed logs.
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # Find all log files (including compressed)
            log_files = list(self.log_dir.glob("*.log*"))
            
            deleted_count = 0
            for log_file in log_files:
                # Skip .gitkeep
                if log_file.name == ".gitkeep":
                    continue
                
                # Check file age
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_date:
                    # Delete old file
                    log_file.unlink()
                    logger.info(f"Deleted old log: {log_file.name} (age: {(datetime.now() - mtime).days} days)")
                    deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old log files")
        
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}", exc_info=True)
    
    async def check_disk_space(self):
        """
        Check disk space and trigger cleanup if below threshold.
        
        If free space < 10%, performs aggressive cleanup:
        1. Delete logs older than 7 days (instead of 30)
        2. Compress all uncompressed logs immediately
        3. Delete old data files
        """
        try:
            # Get disk usage statistics
            stat = shutil.disk_usage(self.log_dir)
            free_space_pct = stat.free / stat.total
            
            logger.debug(f"Disk space: {free_space_pct*100:.1f}% free "
                        f"({stat.free / (1024**3):.2f} GB / {stat.total / (1024**3):.2f} GB)")
            
            if free_space_pct < self.disk_space_threshold:
                logger.warning(f"⚠️ Low disk space: {free_space_pct*100:.1f}% free (threshold: {self.disk_space_threshold*100:.1f}%)")
                logger.warning("Triggering aggressive cleanup...")
                
                # Aggressive cleanup
                await self._aggressive_cleanup()
                
                # Check again after cleanup
                stat = shutil.disk_usage(self.log_dir)
                new_free_space_pct = stat.free / stat.total
                freed_space_gb = (stat.free - stat.free) / (1024**3)
                
                logger.info(f"✅ Cleanup complete: {new_free_space_pct*100:.1f}% free "
                           f"(freed {freed_space_gb:.2f} GB)")
        
        except Exception as e:
            logger.error(f"Error checking disk space: {e}", exc_info=True)
    
    async def _aggressive_cleanup(self):
        """
        Perform aggressive cleanup when disk space is low.
        
        Actions:
        1. Delete logs older than 7 days (instead of 30)
        2. Compress all uncompressed logs older than 1 day
        3. Delete old data files (backups, temp files)
        """
        try:
            # 1. Delete logs older than 7 days
            cutoff_date = datetime.now() - timedelta(days=7)
            log_files = list(self.log_dir.glob("*.log*"))
            
            deleted_count = 0
            for log_file in log_files:
                if log_file.name == ".gitkeep":
                    continue
                
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_date:
                    log_file.unlink()
                    deleted_count += 1
            
            logger.info(f"Aggressive cleanup: Deleted {deleted_count} logs older than 7 days")
            
            # 2. Compress all uncompressed logs older than 1 day (not all logs)
            compression_cutoff = datetime.now() - timedelta(days=1)
            log_files = [f for f in self.log_dir.glob("*.log.*") if not f.name.endswith(".gz")]
            
            compressed_count = 0
            for log_file in log_files:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < compression_cutoff:
                    compressed_path = Path(str(log_file) + ".gz")
                    if not compressed_path.exists():
                        await self._compress_file(log_file, compressed_path)
                        log_file.unlink()
                        compressed_count += 1
            
            logger.info(f"Aggressive cleanup: Compressed {compressed_count} uncompressed logs")
            
            # 3. Delete old data files
            data_dir = Path("data")
            if data_dir.exists():
                deleted_data_count = await self._cleanup_old_data_files(data_dir, days=7)
                logger.info(f"Aggressive cleanup: Deleted {deleted_data_count} old data files")
        
        except Exception as e:
            logger.error(f"Error in aggressive cleanup: {e}", exc_info=True)
    
    async def _cleanup_old_data_files(self, data_dir: Path, days: int = 7) -> int:
        """
        Clean up old data files (backups, temp files).
        
        Args:
            data_dir: Directory containing data files
            days: Delete files older than this many days
            
        Returns:
            Number of files deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0
            
            # Patterns for files to clean up
            patterns = [
                "*.bak",      # Backup files
                "*.tmp",      # Temporary files
                "*.old",      # Old files
                "*_backup_*", # Backup files with timestamp
            ]
            
            for pattern in patterns:
                for file_path in data_dir.glob(pattern):
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_date:
                        file_path.unlink()
                        deleted_count += 1
            
            return deleted_count
        
        except Exception as e:
            logger.error(f"Error cleaning up data files: {e}", exc_info=True)
            return 0
    
    def get_log_stats(self) -> dict:
        """
        Get statistics about log files.
        
        Returns:
            Dictionary with log statistics
        """
        try:
            # Find all log files (including .gz compressed files)
            all_files = list(self.log_dir.glob("*"))
            log_files = [f for f in all_files if f.name != ".gitkeep" and (
                f.name.endswith(".log") or 
                ".log." in f.name or 
                f.name.endswith(".gz")
            )]
            
            total_size = sum(f.stat().st_size for f in log_files)
            compressed_files = [f for f in log_files if f.name.endswith(".gz")]
            uncompressed_files = [f for f in log_files if not f.name.endswith(".gz")]
            
            # Disk usage
            stat = shutil.disk_usage(self.log_dir)
            free_space_pct = stat.free / stat.total
            
            return {
                "total_files": len(log_files),
                "compressed_files": len(compressed_files),
                "uncompressed_files": len(uncompressed_files),
                "total_size_mb": total_size / (1024**2),
                "disk_free_pct": free_space_pct * 100,
                "disk_free_gb": stat.free / (1024**3),
                "disk_total_gb": stat.total / (1024**3),
            }
        
        except Exception as e:
            logger.error(f"Error getting log stats: {e}", exc_info=True)
            return {}


async def main():
    """Test the log manager."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create log manager
    manager = LogManager(
        log_dir="logs",
        retention_days=30,
        compression_age_days=1,
        disk_space_threshold=0.10,
        check_interval_seconds=3600,
    )
    
    # Get initial stats
    stats = manager.get_log_stats()
    logger.info(f"Log stats: {stats}")
    
    # Run one cycle of management tasks
    logger.info("Running log management tasks...")
    await manager.rotate_logs()
    await manager.compress_old_logs()
    await manager.cleanup_old_logs()
    await manager.check_disk_space()
    
    # Get final stats
    stats = manager.get_log_stats()
    logger.info(f"Log stats after cleanup: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
