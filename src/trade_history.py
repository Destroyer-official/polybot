"""
Trade History Database for Polymarket Arbitrage Bot.

Provides SQLite database for persistent trade history storage.

Validates Requirements:
- 19.4: Store trade history in SQLite database
"""

import sqlite3
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from contextlib import contextmanager

from src.models import TradeResult, Opportunity
from src.logging_config import get_logger


class TradeHistoryDB:
    """
    SQLite database for trade history persistence.
    
    Validates Requirement 19.4: Store trade history in SQLite database
    """
    
    def __init__(self, db_path: str = "data/trade_history.db"):
        """
        Initialize trade history database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.logger = get_logger(__name__)
        self.db_path = db_path
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._init_schema()
        
        self.logger.info(f"Trade history database initialized: {db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_schema(self):
        """Initialize database schema with trades table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    status TEXT NOT NULL,
                    
                    -- Opportunity details
                    yes_price TEXT NOT NULL,
                    no_price TEXT NOT NULL,
                    yes_fee TEXT NOT NULL,
                    no_fee TEXT NOT NULL,
                    total_cost TEXT NOT NULL,
                    expected_profit TEXT NOT NULL,
                    profit_percentage TEXT NOT NULL,
                    position_size TEXT NOT NULL,
                    
                    -- Execution details
                    yes_order_id TEXT,
                    no_order_id TEXT,
                    yes_filled INTEGER NOT NULL,
                    no_filled INTEGER NOT NULL,
                    yes_fill_price TEXT,
                    no_fill_price TEXT,
                    
                    -- Financial results
                    actual_cost TEXT NOT NULL,
                    actual_profit TEXT NOT NULL,
                    gas_cost TEXT NOT NULL,
                    net_profit TEXT NOT NULL,
                    
                    -- Transaction hashes
                    yes_tx_hash TEXT,
                    no_tx_hash TEXT,
                    merge_tx_hash TEXT,
                    
                    -- Error information
                    error_message TEXT,
                    
                    -- Cross-platform specific
                    platform_a TEXT,
                    platform_b TEXT
                )
            """)
            
            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON trades(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_strategy 
                ON trades(strategy)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status 
                ON trades(status)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_market_id 
                ON trades(market_id)
            """)
            
            self.logger.info("Database schema initialized")
    
    def insert_trade(self, trade: TradeResult) -> bool:
        """
        Insert a trade record into the database.
        
        Validates Requirement 19.4: Store trade history
        
        Args:
            trade: TradeResult object to store
            
        Returns:
            bool: True if insert successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO trades (
                        trade_id, timestamp, market_id, strategy, status,
                        yes_price, no_price, yes_fee, no_fee, total_cost,
                        expected_profit, profit_percentage, position_size,
                        yes_order_id, no_order_id, yes_filled, no_filled,
                        yes_fill_price, no_fill_price,
                        actual_cost, actual_profit, gas_cost, net_profit,
                        yes_tx_hash, no_tx_hash, merge_tx_hash,
                        error_message, platform_a, platform_b
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trade_id,
                    trade.timestamp.isoformat(),
                    trade.opportunity.market_id,
                    trade.opportunity.strategy,
                    trade.status,
                    str(trade.opportunity.yes_price),
                    str(trade.opportunity.no_price),
                    str(trade.opportunity.yes_fee),
                    str(trade.opportunity.no_fee),
                    str(trade.opportunity.total_cost),
                    str(trade.opportunity.expected_profit),
                    str(trade.opportunity.profit_percentage),
                    str(trade.opportunity.position_size),
                    trade.yes_order_id,
                    trade.no_order_id,
                    1 if trade.yes_filled else 0,
                    1 if trade.no_filled else 0,
                    str(trade.yes_fill_price) if trade.yes_fill_price else None,
                    str(trade.no_fill_price) if trade.no_fill_price else None,
                    str(trade.actual_cost),
                    str(trade.actual_profit),
                    str(trade.gas_cost),
                    str(trade.net_profit),
                    trade.yes_tx_hash,
                    trade.no_tx_hash,
                    trade.merge_tx_hash,
                    trade.error_message,
                    trade.opportunity.platform_a,
                    trade.opportunity.platform_b,
                ))
                
                self.logger.debug(f"Trade inserted: {trade.trade_id}")
                return True
                
        except sqlite3.IntegrityError as e:
            self.logger.warning(f"Trade already exists: {trade.trade_id}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to insert trade: {e}")
            return False
    
    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a trade by ID.
        
        Args:
            trade_id: Trade ID to retrieve
            
        Returns:
            Optional[Dict]: Trade data if found, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve trade {trade_id}: {e}")
            return None
    
    def get_trades_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve trades within a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List[Dict]: List of trade records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM trades 
                    WHERE timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp DESC
                """, (start_date.isoformat(), end_date.isoformat()))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve trades by date range: {e}")
            return []
    
    def get_trades_by_strategy(
        self,
        strategy: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve trades by strategy type.
        
        Args:
            strategy: Strategy type (internal, cross_platform, etc.)
            limit: Optional limit on number of results
            
        Returns:
            List[Dict]: List of trade records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT * FROM trades 
                    WHERE strategy = ?
                    ORDER BY timestamp DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query, (strategy,))
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve trades by strategy: {e}")
            return []
    
    def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve most recent trades.
        
        Args:
            limit: Maximum number of trades to retrieve
            
        Returns:
            List[Dict]: List of trade records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM trades 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve recent trades: {e}")
            return []
    
    def get_successful_trades(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve successful trades only.
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List[Dict]: List of successful trade records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT * FROM trades 
                    WHERE status = 'success'
                    ORDER BY timestamp DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve successful trades: {e}")
            return []
    
    def get_failed_trades(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve failed trades only.
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List[Dict]: List of failed trade records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT * FROM trades 
                    WHERE status != 'success'
                    ORDER BY timestamp DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve failed trades: {e}")
            return []
    
    def get_total_trade_count(self) -> int:
        """
        Get total number of trades in database.
        
        Returns:
            int: Total trade count
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM trades")
                return cursor.fetchone()[0]
                
        except Exception as e:
            self.logger.error(f"Failed to get trade count: {e}")
            return 0
    
    def delete_old_trades(self, days: int = 90) -> int:
        """
        Delete trades older than specified days.
        
        Args:
            days: Number of days to keep (default 90)
            
        Returns:
            int: Number of trades deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM trades 
                    WHERE timestamp < ?
                """, (cutoff_date.isoformat(),))
                
                deleted_count = cursor.rowcount
                self.logger.info(f"Deleted {deleted_count} trades older than {days} days")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to delete old trades: {e}")
            return 0
