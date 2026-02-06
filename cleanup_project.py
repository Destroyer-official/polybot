#!/usr/bin/env python3
"""
Project Cleanup Script.

Removes unnecessary files and organizes the project for production.
"""

import os
import shutil
from pathlib import Path

# Files to keep (production essentials)
KEEP_FILES = {
    # Core application
    'bot.py',
    'config.py',
    'setup_bot.py',
    'requirements.txt',
    'README.md',
    
    # Configuration
    '.env.example',
    '.env.template',
    '.gitignore',
    
    # Documentation
    'PRODUCTION_READY_ANALYSIS.md',
    'PRODUCTION_DEPLOYMENT_GUIDE.md',
    'ENV_SETUP_GUIDE.md',
    'HOW_TO_RUN.md',
    
    # Deployment
    'run_bot.sh',
    'money.pem',
}

# Directories to keep
KEEP_DIRS = {
    'src',
    'config',
    'tests',
    'deployment',
    'logs',
    'rust_core',
    '.git',
    '.github',
    '.kiro',
    'data',
    'docs',
}

# Patterns to remove (debug/test files)
REMOVE_PATTERNS = [
    'check_*.py',
    'debug_*.py',
    'test_*.py',  # Keep tests/ directory but remove root test files
    'quick_*.py',
    'find_*.py',
    'get_*.py',
    'wait_*.py',
    'swap_*.py',
    'withdraw_*.py',
    'deposit_*.py',
    'auto_*.py',
    'cross_*.py',
    'BALANCE_*.py',
    'BALANCE_*.md',
    'BOT_*.md',
    'BRIDGE_*.md',
    'COMPREHENSIVE_*.md',
    'DEPLOYMENT_*.md',
    'DEPOSIT_*.md',
    'DYNAMIC_*.md',
    'FAST_*.md',
    'FINAL_*.md',
    'FIX_*.md',
    'FULL_*.py',
    'HONEST_*.md',
    'HOW_*.md',
    'IMPLEMENTATION_*.md',
    'IMPROVEMENTS_*.md',
    'LIVE_*.md',
    'MARKET_*.md',
    'OPTIMIZATION_*.md',
    'OPTIMIZED_*.md',
    'POLYMARKET_*.md',
    'PRE_*.md',
    'QUICK_*.md',
    'READY_*.md',
    'REAL_*.md',
    'RESTART_*.py',
    'RUN_*.md',
    'SIMPLE_*.md',
    'SOLUTION_*.md',
    'START_*.py',
    'START_*.bat',
    'START_*.md',
    'START_*.sh',
    'STOP_*.md',
    'TASK_*.md',
    'TEST_*.md',
    'UNICODE_*.md',
    'URGENT_*.txt',
    'USE_*.md',
    'VALIDATION_*.md',
    'WHAT_*.md',
    'WHY_*.md',
    'WINNING_*.py',
    'WINNING_*.md',
    'DO_THIS_NOW.txt',
    'RUN_NOW.txt',
    '*.log',
    'state.json',
    '.coverage',
]


def should_remove(path: Path) -> bool:
    """Check if file should be removed."""
    # Keep if in KEEP_FILES
    if path.name in KEEP_FILES:
        return False
    
    # Keep if in KEEP_DIRS
    if path.is_dir() and path.name in KEEP_DIRS:
        return False
    
    # Remove if matches pattern
    for pattern in REMOVE_PATTERNS:
        if path.match(pattern):
            return True
    
    return False


def cleanup_project(dry_run: bool = True):
    """
    Clean up project files.
    
    Args:
        dry_run: If True, only show what would be removed
    """
    root = Path('.')
    removed_count = 0
    kept_count = 0
    
    print("=" * 80)
    print("PROJECT CLEANUP")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no files will be deleted)' if dry_run else 'LIVE (files will be deleted)'}")
    print()
    
    # Scan root directory
    for item in root.iterdir():
        # Skip hidden files/dirs except .git, .github, .kiro
        if item.name.startswith('.') and item.name not in {'.git', '.github', '.kiro', '.gitignore', '.env.example', '.env.template'}:
            continue
        
        # Skip directories we want to keep
        if item.is_dir() and item.name in KEEP_DIRS:
            kept_count += 1
            continue
        
        # Check if should remove
        if should_remove(item):
            print(f"{'[DRY RUN] Would remove' if dry_run else 'Removing'}: {item}")
            if not dry_run:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            removed_count += 1
        else:
            kept_count += 1
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Files/dirs to remove: {removed_count}")
    print(f"Files/dirs to keep: {kept_count}")
    
    if dry_run:
        print()
        print("This was a DRY RUN. No files were actually deleted.")
        print("To perform actual cleanup, run:")
        print("  python cleanup_project.py --live")
    else:
        print()
        print("✅ Cleanup complete!")
    
    print("=" * 80)


def create_archive():
    """Create archive of removed files before cleanup."""
    import tarfile
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"backup_before_cleanup_{timestamp}.tar.gz"
    
    print(f"Creating backup archive: {archive_name}")
    
    with tarfile.open(archive_name, "w:gz") as tar:
        root = Path('.')
        for item in root.iterdir():
            if should_remove(item):
                tar.add(item)
    
    print(f"✅ Backup created: {archive_name}")
    return archive_name


if __name__ == "__main__":
    import sys
    
    # Check for --live flag
    live_mode = '--live' in sys.argv
    create_backup = '--backup' in sys.argv
    
    if create_backup:
        print("Creating backup before cleanup...")
        archive = create_archive()
        print()
    
    if live_mode:
        response = input("⚠️  This will permanently delete files. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cleanup cancelled.")
            sys.exit(0)
    
    cleanup_project(dry_run=not live_mode)
