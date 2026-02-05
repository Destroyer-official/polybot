"""
Historical data loader for backtesting framework.

Loads market data from CSV/database and supports date range filtering.
Validates Requirement 12.1.
"""

import csv
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Iterator
import logging

from src.models import Market

logger = logging.getLogger(__name__)


class BacktestDataLoader:
    """
    Loads historical market data for backtesting.
    
    Supports loading from:
    - CSV files with market snapshots
    - SQLite database with historical data
    
    Validates Requirement 12.1: Load market data from CSV/database with date range filtering
    """
    
    def __init__(self, data_source: str):
        """
        Initialize the data loader.
        
        Args:
            data_source: Path to CSV file or SQLite database
        """
        self.data_source = Path(data_source)
        self.is_csv = self.data_source.suffix.lower() == '.csv'
        self.is_db = self.data_source.suffix.lower() in ['.db', '.sqlite', '.sqlite3']
        
        if not self.is_csv and not self.is_db:
            raise ValueError(f"Unsupported data source format: {self.data_source.suffix}")
        
        if not self.data_source.exists():
            raise FileNotFoundError(f"Data source not found: {self.data_source}")
        
        logger.info(f"Initialized BacktestDataLoader with source: {self.data_source}")
    
    def load_markets(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        asset_filter: Optional[List[str]] = None
    ) -> List[Market]:
        """
        Load historical market data with optional filtering.
        
        Args:
            start_date: Optional start date for filtering (inclusive)
            end_date: Optional end date for filtering (inclusive)
            asset_filter: Optional list of assets to filter (e.g., ["BTC", "ETH"])
            
        Returns:
            List[Market]: List of historical market snapshots
            
        Validates Requirement 12.1: Support date range filtering
        """
        if self.is_csv:
            markets = self._load_from_csv()
        else:
            markets = self._load_from_database()
        
        # Apply filters
        filtered_markets = self._apply_filters(markets, start_date, end_date, asset_filter)
        
        logger.info(
            f"Loaded {len(filtered_markets)} markets "
            f"(filtered from {len(markets)} total)"
        )
        
        return filtered_markets
    
    def load_markets_streaming(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        asset_filter: Optional[List[str]] = None
    ) -> Iterator[Market]:
        """
        Stream historical market data without loading all into memory.
        
        Useful for large datasets that don't fit in memory.
        
        Args:
            start_date: Optional start date for filtering (inclusive)
            end_date: Optional end date for filtering (inclusive)
            asset_filter: Optional list of assets to filter (e.g., ["BTC", "ETH"])
            
        Yields:
            Market: Individual market snapshots
        """
        if self.is_csv:
            yield from self._stream_from_csv(start_date, end_date, asset_filter)
        else:
            yield from self._stream_from_database(start_date, end_date, asset_filter)
    
    def _load_from_csv(self) -> List[Market]:
        """Load all markets from CSV file."""
        markets = []
        
        with open(self.data_source, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    market = self._parse_csv_row(row)
                    markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse CSV row: {e}, row: {row}")
                    continue
        
        return markets
    
    def _stream_from_csv(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        asset_filter: Optional[List[str]]
    ) -> Iterator[Market]:
        """Stream markets from CSV file."""
        with open(self.data_source, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    market = self._parse_csv_row(row)
                    
                    # Apply filters
                    if not self._passes_filters(market, start_date, end_date, asset_filter):
                        continue
                    
                    yield market
                    
                except Exception as e:
                    logger.warning(f"Failed to parse CSV row: {e}")
                    continue
    
    def _parse_csv_row(self, row: dict) -> Market:
        """
        Parse a CSV row into a Market object.
        
        Expected CSV columns:
        - market_id, question, asset, outcomes, yes_price, no_price,
          yes_token_id, no_token_id, volume, liquidity, end_time, resolution_source
        """
        # Parse outcomes (comma-separated string to list)
        outcomes = row['outcomes'].split(',') if ',' in row['outcomes'] else ['YES', 'NO']
        
        # Parse datetime
        end_time = datetime.fromisoformat(row['end_time'])
        
        return Market(
            market_id=row['market_id'],
            question=row['question'],
            asset=row['asset'],
            outcomes=outcomes,
            yes_price=Decimal(row['yes_price']),
            no_price=Decimal(row['no_price']),
            yes_token_id=row['yes_token_id'],
            no_token_id=row['no_token_id'],
            volume=Decimal(row['volume']),
            liquidity=Decimal(row['liquidity']),
            end_time=end_time,
            resolution_source=row['resolution_source']
        )
    
    def _load_from_database(self) -> List[Market]:
        """Load all markets from SQLite database."""
        markets = []
        
        conn = sqlite3.connect(self.data_source)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    market_id, question, asset, outcomes, yes_price, no_price,
                    yes_token_id, no_token_id, volume, liquidity, end_time, resolution_source
                FROM markets
                ORDER BY end_time ASC
            """)
            
            for row in cursor.fetchall():
                try:
                    market = self._parse_db_row(row)
                    markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse DB row: {e}")
                    continue
        
        finally:
            conn.close()
        
        return markets
    
    def _stream_from_database(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        asset_filter: Optional[List[str]]
    ) -> Iterator[Market]:
        """Stream markets from SQLite database."""
        conn = sqlite3.connect(self.data_source)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Build query with filters
            query = """
                SELECT 
                    market_id, question, asset, outcomes, yes_price, no_price,
                    yes_token_id, no_token_id, volume, liquidity, end_time, resolution_source
                FROM markets
                WHERE 1=1
            """
            params = []
            
            if start_date:
                query += " AND end_time >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND end_time <= ?"
                params.append(end_date.isoformat())
            
            if asset_filter:
                placeholders = ','.join('?' * len(asset_filter))
                query += f" AND asset IN ({placeholders})"
                params.extend(asset_filter)
            
            query += " ORDER BY end_time ASC"
            
            cursor.execute(query, params)
            
            for row in cursor.fetchall():
                try:
                    market = self._parse_db_row(row)
                    yield market
                except Exception as e:
                    logger.warning(f"Failed to parse DB row: {e}")
                    continue
        
        finally:
            conn.close()
    
    def _parse_db_row(self, row: sqlite3.Row) -> Market:
        """Parse a database row into a Market object."""
        # Parse outcomes (stored as comma-separated string)
        outcomes = row['outcomes'].split(',') if ',' in row['outcomes'] else ['YES', 'NO']
        
        # Parse datetime
        end_time = datetime.fromisoformat(row['end_time'])
        
        return Market(
            market_id=row['market_id'],
            question=row['question'],
            asset=row['asset'],
            outcomes=outcomes,
            yes_price=Decimal(str(row['yes_price'])),
            no_price=Decimal(str(row['no_price'])),
            yes_token_id=row['yes_token_id'],
            no_token_id=row['no_token_id'],
            volume=Decimal(str(row['volume'])),
            liquidity=Decimal(str(row['liquidity'])),
            end_time=end_time,
            resolution_source=row['resolution_source']
        )
    
    def _apply_filters(
        self,
        markets: List[Market],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        asset_filter: Optional[List[str]]
    ) -> List[Market]:
        """Apply date and asset filters to market list."""
        filtered = []
        
        for market in markets:
            if self._passes_filters(market, start_date, end_date, asset_filter):
                filtered.append(market)
        
        return filtered
    
    def _passes_filters(
        self,
        market: Market,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        asset_filter: Optional[List[str]]
    ) -> bool:
        """Check if a market passes the specified filters."""
        # Date range filter
        if start_date and market.end_time < start_date:
            return False
        
        if end_date and market.end_time > end_date:
            return False
        
        # Asset filter
        if asset_filter and market.asset not in asset_filter:
            return False
        
        return True
    
    def get_date_range(self) -> tuple[Optional[datetime], Optional[datetime]]:
        """
        Get the date range of available data.
        
        Returns:
            tuple: (earliest_date, latest_date) or (None, None) if no data
        """
        if self.is_csv:
            markets = self._load_from_csv()
        else:
            conn = sqlite3.connect(self.data_source)
            cursor = conn.cursor()
            
            try:
                cursor.execute("SELECT MIN(end_time), MAX(end_time) FROM markets")
                row = cursor.fetchone()
                
                if row and row[0] and row[1]:
                    return (
                        datetime.fromisoformat(row[0]),
                        datetime.fromisoformat(row[1])
                    )
                return (None, None)
            
            finally:
                conn.close()
        
        if not markets:
            return (None, None)
        
        dates = [m.end_time for m in markets]
        return (min(dates), max(dates))
    
    def get_available_assets(self) -> List[str]:
        """
        Get list of unique assets in the dataset.
        
        Returns:
            List[str]: Sorted list of unique asset symbols
        """
        if self.is_csv:
            markets = self._load_from_csv()
            assets = set(m.asset for m in markets)
        else:
            conn = sqlite3.connect(self.data_source)
            cursor = conn.cursor()
            
            try:
                cursor.execute("SELECT DISTINCT asset FROM markets ORDER BY asset")
                assets = set(row[0] for row in cursor.fetchall())
            finally:
                conn.close()
        
        return sorted(assets)
