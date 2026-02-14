"""
Unit tests for automatic log management system.

Tests Requirements 11.5, 11.12:
- Daily log rotation with 30-day retention
- Automatic compression of old logs
- Disk space monitoring (<10% triggers cleanup)
- Automatic cleanup of old data
"""

import asyncio
import gzip
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
import pytest

from src.log_manager import LogManager

logger = logging.getLogger(__name__)


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def log_manager(temp_log_dir):
    """Create a log manager instance with test configuration."""
    return LogManager(
        log_dir=temp_log_dir,
        retention_days=30,
        compression_age_days=1,
        disk_space_threshold=0.10,
        check_interval_seconds=3600,
    )


def create_test_log_file(log_dir: Path, name: str, age_days: int = 0, content: str = "test log content\n"):
    """Create a test log file with specified age."""
    log_file = log_dir / name
    log_file.write_text(content * 100)  # Make it somewhat large
    
    # Set modification time to simulate age
    if age_days > 0:
        old_time = time.time() - (age_days * 86400)
        os.utime(log_file, (old_time, old_time))
    
    return log_file


class TestLogRotation:
    """Test log rotation functionality."""
    
    @pytest.mark.asyncio
    async def test_rotate_old_logs(self, log_manager, temp_log_dir):
        """Test that logs from previous days are rotated."""
        log_dir = Path(temp_log_dir)
        
        # Create a log file from yesterday
        old_log = create_test_log_file(log_dir, "bot.log", age_days=1)
        
        # Rotate logs
        await log_manager.rotate_logs()
        
        # Check that file was rotated
        assert not old_log.exists(), "Old log file should be rotated"
        
        # Check that rotated file exists with date suffix
        rotated_files = list(log_dir.glob("bot.log.*"))
        assert len(rotated_files) == 1, "Should have one rotated file"
        assert rotated_files[0].name.startswith("bot.log."), "Rotated file should have date suffix"
    
    @pytest.mark.asyncio
    async def test_dont_rotate_current_logs(self, log_manager, temp_log_dir):
        """Test that logs from today are not rotated."""
        log_dir = Path(temp_log_dir)
        
        # Create a log file from today
        current_log = create_test_log_file(log_dir, "bot.log", age_days=0)
        
        # Rotate logs
        await log_manager.rotate_logs()
        
        # Check that file was NOT rotated
        assert current_log.exists(), "Current log file should not be rotated"
        
        # Check that no rotated files exist
        rotated_files = list(log_dir.glob("bot.log.*"))
        assert len(rotated_files) == 0, "Should have no rotated files"


class TestLogCompression:
    """Test log compression functionality."""
    
    @pytest.mark.asyncio
    async def test_compress_old_logs(self, log_manager, temp_log_dir):
        """Test that old rotated logs are compressed."""
        log_dir = Path(temp_log_dir)
        
        # Create a rotated log file from 2 days ago
        old_log = create_test_log_file(log_dir, "bot.log.2024-01-01", age_days=2)
        original_content = old_log.read_text()
        
        # Compress logs
        await log_manager.compress_old_logs()
        
        # Check that original file was removed
        assert not old_log.exists(), "Original log file should be removed after compression"
        
        # Check that compressed file exists
        compressed_file = Path(str(old_log) + ".gz")
        assert compressed_file.exists(), "Compressed file should exist"
        
        # Verify compressed content
        with gzip.open(compressed_file, 'rt') as f:
            decompressed_content = f.read()
        assert decompressed_content == original_content, "Decompressed content should match original"
    
    @pytest.mark.asyncio
    async def test_dont_compress_recent_logs(self, log_manager, temp_log_dir):
        """Test that recent rotated logs are not compressed."""
        log_dir = Path(temp_log_dir)
        
        # Create a rotated log file from today
        recent_log = create_test_log_file(log_dir, "bot.log.2024-01-15", age_days=0)
        
        # Compress logs
        await log_manager.compress_old_logs()
        
        # Check that file was NOT compressed
        assert recent_log.exists(), "Recent log file should not be compressed"
        
        # Check that no compressed file exists
        compressed_file = Path(str(recent_log) + ".gz")
        assert not compressed_file.exists(), "Compressed file should not exist"


class TestLogCleanup:
    """Test log cleanup functionality."""
    
    @pytest.mark.asyncio
    async def test_cleanup_old_logs(self, log_manager, temp_log_dir):
        """Test that logs older than retention period are deleted."""
        log_dir = Path(temp_log_dir)
        
        # Create logs of various ages
        old_log = create_test_log_file(log_dir, "bot.log.2023-01-01", age_days=365)
        recent_log = create_test_log_file(log_dir, "bot.log.2024-01-01", age_days=10)
        
        # Cleanup logs
        await log_manager.cleanup_old_logs()
        
        # Check that old log was deleted
        assert not old_log.exists(), "Old log file should be deleted"
        
        # Check that recent log was kept
        assert recent_log.exists(), "Recent log file should be kept"
    
    @pytest.mark.asyncio
    async def test_cleanup_compressed_logs(self, log_manager, temp_log_dir):
        """Test that compressed logs are also cleaned up."""
        log_dir = Path(temp_log_dir)
        
        # Create an old compressed log
        old_log = create_test_log_file(log_dir, "bot.log.2023-01-01.gz", age_days=365)
        
        # Cleanup logs
        await log_manager.cleanup_old_logs()
        
        # Check that old compressed log was deleted
        assert not old_log.exists(), "Old compressed log file should be deleted"


class TestDiskSpaceMonitoring:
    """Test disk space monitoring functionality."""
    
    @pytest.mark.asyncio
    async def test_check_disk_space_normal(self, log_manager, temp_log_dir):
        """Test disk space check when space is sufficient."""
        # This should not trigger cleanup
        await log_manager.check_disk_space()
        
        # No assertions needed - just verify it doesn't crash
    
    @pytest.mark.asyncio
    async def test_aggressive_cleanup_deletes_old_logs(self, log_manager, temp_log_dir):
        """Test that aggressive cleanup deletes logs older than 7 days."""
        log_dir = Path(temp_log_dir)
        
        # Create logs of various ages
        very_old_log = create_test_log_file(log_dir, "bot.log.2024-01-01", age_days=10)
        old_log = create_test_log_file(log_dir, "bot.log.2024-01-08", age_days=8)
        recent_log = create_test_log_file(log_dir, "bot.log.2024-01-14", age_days=2)
        
        # Trigger aggressive cleanup
        await log_manager._aggressive_cleanup()
        
        # Check that logs older than 7 days were deleted
        assert not very_old_log.exists(), "Very old log should be deleted"
        assert not old_log.exists(), "Old log should be deleted"
        
        # Check that recent log was kept (may be compressed)
        assert recent_log.exists() or Path(str(recent_log) + ".gz").exists(), \
            "Recent log should be kept (either uncompressed or compressed)"
    
    @pytest.mark.asyncio
    async def test_aggressive_cleanup_compresses_all_logs(self, log_manager, temp_log_dir):
        """Test that aggressive cleanup compresses all uncompressed logs."""
        log_dir = Path(temp_log_dir)
        
        # Create uncompressed rotated logs
        log1 = create_test_log_file(log_dir, "bot.log.2024-01-14", age_days=2)
        log2 = create_test_log_file(log_dir, "bot.log.2024-01-13", age_days=3)
        
        # Trigger aggressive cleanup
        await log_manager._aggressive_cleanup()
        
        # Check that logs were compressed
        assert not log1.exists(), "Log 1 should be compressed"
        assert not log2.exists(), "Log 2 should be compressed"
        
        # Check that compressed files exist
        assert Path(str(log1) + ".gz").exists(), "Compressed log 1 should exist"
        assert Path(str(log2) + ".gz").exists(), "Compressed log 2 should exist"


class TestLogStats:
    """Test log statistics functionality."""
    
    def test_get_log_stats(self, log_manager, temp_log_dir):
        """Test getting log statistics."""
        log_dir = Path(temp_log_dir)
        
        # Create various log files
        create_test_log_file(log_dir, "bot.log", age_days=0)
        create_test_log_file(log_dir, "bot.log.2024-01-14", age_days=2)
        create_test_log_file(log_dir, "bot.log.2024-01-13.gz", age_days=3)
        
        # Get stats
        stats = log_manager.get_log_stats()
        
        # Verify stats
        assert stats["total_files"] == 3, "Should have 3 log files"
        assert stats["compressed_files"] == 1, "Should have 1 compressed file"
        assert stats["uncompressed_files"] == 2, "Should have 2 uncompressed files"
        assert stats["total_size_mb"] > 0, "Total size should be > 0"
        assert stats["disk_free_pct"] > 0, "Disk free percentage should be > 0"
        assert stats["disk_free_gb"] > 0, "Disk free GB should be > 0"
        assert stats["disk_total_gb"] > 0, "Disk total GB should be > 0"


class TestIntegration:
    """Integration tests for log manager."""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle(self, log_manager, temp_log_dir):
        """Test full log lifecycle: create -> rotate -> compress -> cleanup."""
        log_dir = Path(temp_log_dir)
        
        # 1. Create logs of various ages
        current_log = create_test_log_file(log_dir, "bot.log", age_days=0)
        old_log = create_test_log_file(log_dir, "old.log", age_days=1)
        very_old_log = create_test_log_file(log_dir, "very_old.log", age_days=40)
        
        # 2. Rotate logs
        await log_manager.rotate_logs()
        
        # Current log should remain
        assert current_log.exists()
        
        # Old log should be rotated
        assert not old_log.exists()
        rotated_files = list(log_dir.glob("old.log.*"))
        assert len(rotated_files) == 1
        
        # 3. Compress old logs
        await log_manager.compress_old_logs()
        
        # Rotated log should be compressed (if old enough)
        # Note: This depends on compression_age_days setting
        
        # 4. Cleanup old logs
        await log_manager.cleanup_old_logs()
        
        # Very old log should be deleted
        assert not very_old_log.exists()
        
        # 5. Check disk space
        await log_manager.check_disk_space()
        
        # Should complete without errors


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
