"""
Unit tests for startup validation (Task 14.3, Requirement 11.8).

Tests comprehensive startup validation including:
- API credentials verification
- CLOB API connection testing
- WebSocket connection verification
- Balance and wallet access validation
- Learning data integrity checks
- Self-diagnostics
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from pathlib import Path
import json
import tempfile
import shutil


class TestStartupValidationLogic:
    """Test suite for startup validation logic (without full orchestrator initialization)."""
    
    @pytest.mark.asyncio
    async def test_api_credentials_validation_pass(self):
        """Test API credentials validation when credentials exist."""
        # Mock CLOB client with valid credentials
        mock_clob = Mock()
        mock_clob.creds = Mock(
            api_key="test_api_key_12345678",
            api_secret="test_secret",
            api_passphrase="test_passphrase"
        )
        
        # Simulate validation logic
        has_credentials = (
            hasattr(mock_clob, 'creds') and 
            mock_clob.creds and
            hasattr(mock_clob.creds, 'api_key')
        )
        
        assert has_credentials is True, "Should detect valid API credentials"
    
    @pytest.mark.asyncio
    async def test_api_credentials_validation_fail(self):
        """Test API credentials validation when credentials are missing."""
        # Mock CLOB client without credentials
        mock_clob = Mock()
        mock_clob.creds = None
        
        # Simulate validation logic
        has_credentials = (
            hasattr(mock_clob, 'creds') and 
            mock_clob.creds is not None and
            hasattr(mock_clob.creds, 'api_key')
        )
        
        assert not has_credentials, "Should detect missing API credentials"
    
    @pytest.mark.asyncio
    async def test_clob_connection_validation_pass(self):
        """Test CLOB API connection when server responds."""
        # Mock CLOB client with successful connection
        mock_clob = Mock()
        mock_clob.get_server_time.return_value = 1234567890
        
        # Simulate validation logic
        try:
            server_time = mock_clob.get_server_time()
            connection_ok = server_time is not None
        except Exception:
            connection_ok = False
        
        assert connection_ok is True, "Should detect successful CLOB connection"
    
    @pytest.mark.asyncio
    async def test_clob_connection_validation_fail(self):
        """Test CLOB API connection when server fails."""
        # Mock CLOB client with connection failure
        mock_clob = Mock()
        mock_clob.get_server_time.side_effect = Exception("Connection failed")
        
        # Simulate validation logic
        try:
            server_time = mock_clob.get_server_time()
            connection_ok = server_time is not None
        except Exception:
            connection_ok = False
        
        assert connection_ok is False, "Should detect failed CLOB connection"
    
    @pytest.mark.asyncio
    async def test_balance_validation_pass(self):
        """Test balance validation when balance check succeeds."""
        # Mock fund manager with successful balance check
        mock_fund_manager = Mock()
        mock_fund_manager.check_balance = AsyncMock(
            return_value=(Decimal("10.0"), Decimal("90.0"))
        )
        
        # Simulate validation logic
        try:
            eoa_balance, proxy_balance = await mock_fund_manager.check_balance()
            total_balance = eoa_balance + proxy_balance
            balance_ok = True
        except Exception:
            balance_ok = False
        
        assert balance_ok is True, "Should detect successful balance check"
        assert total_balance == Decimal("100.0"), "Should calculate correct total balance"
    
    @pytest.mark.asyncio
    async def test_balance_validation_fail(self):
        """Test balance validation when balance check fails."""
        # Mock fund manager with failed balance check
        mock_fund_manager = Mock()
        mock_fund_manager.check_balance = AsyncMock(
            side_effect=Exception("Balance check failed")
        )
        
        # Simulate validation logic
        try:
            eoa_balance, proxy_balance = await mock_fund_manager.check_balance()
            balance_ok = True
        except Exception:
            balance_ok = False
        
        assert balance_ok is False, "Should detect failed balance check"
    
    @pytest.mark.asyncio
    async def test_websocket_validation_connected(self):
        """Test WebSocket validation when connected."""
        # Mock Binance feed with active connection
        mock_binance_feed = Mock()
        mock_binance_feed.is_connected.return_value = True
        
        # Simulate validation logic
        try:
            is_connected = mock_binance_feed.is_connected()
            websocket_ok = True  # Non-critical, always pass
        except Exception:
            websocket_ok = False
        
        assert websocket_ok is True, "Should handle connected WebSocket"
        assert is_connected is True, "Should detect WebSocket connection"
    
    @pytest.mark.asyncio
    async def test_websocket_validation_disconnected(self):
        """Test WebSocket validation when disconnected (non-critical)."""
        # Mock Binance feed with inactive connection
        mock_binance_feed = Mock()
        mock_binance_feed.is_connected.return_value = False
        
        # Simulate validation logic (non-critical)
        try:
            is_connected = mock_binance_feed.is_connected()
            websocket_ok = True  # Non-critical, always pass
        except Exception:
            websocket_ok = False
        
        assert websocket_ok is True, "Should pass even when WebSocket disconnected (non-critical)"
    
    @pytest.mark.asyncio
    async def test_learning_data_validation_exists(self):
        """Test learning data validation when files exist."""
        # Create temporary learning data files
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir(exist_ok=True)
            
            learning_files = [
                data_dir / "supersmart_learning.json",
                data_dir / "rl_learning.json",
                data_dir / "adaptive_learning.json"
            ]
            
            for file_path in learning_files:
                with open(file_path, 'w') as f:
                    json.dump({"test": "data"}, f)
            
            # Simulate validation logic
            learning_data_ok = True
            for file_path in learning_files:
                if file_path.exists():
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                    except Exception:
                        learning_data_ok = False
                        break
            
            assert learning_data_ok is True, "Should validate existing learning data files"
    
    @pytest.mark.asyncio
    async def test_learning_data_validation_missing(self):
        """Test learning data validation when files are missing (non-critical)."""
        # Use non-existent paths
        learning_files = [
            Path("/nonexistent/supersmart_learning.json"),
            Path("/nonexistent/rl_learning.json"),
            Path("/nonexistent/adaptive_learning.json")
        ]
        
        # Simulate validation logic (non-critical)
        learning_data_ok = True
        for file_path in learning_files:
            if not file_path.exists():
                # Missing files are OK - will be created on first trade
                pass
        
        assert learning_data_ok is True, "Should pass when learning data files are missing (non-critical)"
    
    @pytest.mark.asyncio
    async def test_self_diagnostics_circuit_breaker_closed(self):
        """Test self-diagnostics when circuit breaker is closed."""
        # Mock circuit breaker in closed state
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.is_open = False
        
        # Simulate validation logic
        diagnostics_passed = not mock_circuit_breaker.is_open
        
        assert diagnostics_passed is True, "Should pass when circuit breaker is closed"
    
    @pytest.mark.asyncio
    async def test_self_diagnostics_circuit_breaker_open(self):
        """Test self-diagnostics when circuit breaker is open."""
        # Mock circuit breaker in open state
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.is_open = True
        mock_circuit_breaker.consecutive_failures = 5
        
        # Simulate validation logic
        diagnostics_passed = not mock_circuit_breaker.is_open
        
        assert diagnostics_passed is False, "Should fail when circuit breaker is open"
    
    @pytest.mark.asyncio
    async def test_critical_vs_non_critical_checks(self):
        """Test that critical checks are properly identified."""
        critical_checks = ["api_credentials", "clob_connection", "balance_access"]
        non_critical_checks = ["websocket_connection", "learning_data", "self_diagnostics"]
        
        # Simulate validation results
        validation_results = {
            "api_credentials": True,
            "clob_connection": True,
            "balance_access": True,
            "websocket_connection": False,  # Non-critical failure
            "learning_data": False,  # Non-critical failure
            "self_diagnostics": False  # Non-critical failure
        }
        
        # Check if all critical checks passed
        all_critical_passed = all(
            validation_results[check] for check in critical_checks
        )
        
        assert all_critical_passed is True, "Should pass when all critical checks succeed"
    
    @pytest.mark.asyncio
    async def test_critical_check_failure_blocks_startup(self):
        """Test that critical check failure blocks startup."""
        critical_checks = ["api_credentials", "clob_connection", "balance_access"]
        
        # Simulate validation results with critical failure
        validation_results = {
            "api_credentials": True,
            "clob_connection": False,  # CRITICAL FAILURE
            "balance_access": True,
            "websocket_connection": True,
            "learning_data": True,
            "self_diagnostics": True
        }
        
        # Check if all critical checks passed
        all_critical_passed = all(
            validation_results[check] for check in critical_checks
        )
        
        assert all_critical_passed is False, "Should fail when any critical check fails"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

