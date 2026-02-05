"""
Unit tests for configuration management.

Tests configuration loading, validation, and error handling.
"""

import pytest
import os
from decimal import Decimal
from pathlib import Path
import tempfile
import yaml

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import Config, load_config

# Use a valid Ethereum address for testing (Vitalik's address)
TEST_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_valid_config(self):
        """Test that valid configuration passes validation."""
        config = Config(
            private_key="0x" + "1" * 64,
            wallet_address=TEST_ADDRESS,
            polygon_rpc_url="https://polygon-rpc.com",
        )
        
        assert config.private_key == "0x" + "1" * 64
        # Address should be converted to checksum format
        assert config.wallet_address.lower() == TEST_ADDRESS.lower()
        assert config.polygon_rpc_url == "https://polygon-rpc.com"
    
    def test_missing_private_key(self):
        """Test that missing private key raises error."""
        with pytest.raises(ValueError, match="private_key is required"):
            Config(
                private_key="",
                wallet_address=TEST_ADDRESS,
                polygon_rpc_url="https://polygon-rpc.com",
            )
    
    def test_invalid_wallet_address(self):
        """Test that invalid wallet address raises error."""
        with pytest.raises(ValueError, match="wallet_address is not a valid Ethereum address"):
            Config(
                private_key="0x" + "1" * 64,
                wallet_address="invalid_address",
                polygon_rpc_url="https://polygon-rpc.com",
            )
    
    def test_invalid_rpc_url(self):
        """Test that invalid RPC URL raises error."""
        with pytest.raises(ValueError, match="polygon_rpc_url must be a valid URL"):
            Config(
                private_key="0x" + "1" * 64,
                wallet_address=TEST_ADDRESS,
                polygon_rpc_url="not_a_url",
            )
    
    def test_negative_stake_amount(self):
        """Test that negative stake amount raises error."""
        with pytest.raises(ValueError, match="stake_amount must be positive"):
            Config(
                private_key="0x" + "1" * 64,
                wallet_address=TEST_ADDRESS,
                polygon_rpc_url="https://polygon-rpc.com",
                stake_amount=Decimal("-10.0"),
            )
    
    def test_invalid_profit_threshold(self):
        """Test that invalid profit threshold raises error."""
        with pytest.raises(ValueError, match="min_profit_threshold must be between 0 and 1"):
            Config(
                private_key="0x" + "1" * 64,
                wallet_address=TEST_ADDRESS,
                polygon_rpc_url="https://polygon-rpc.com",
                min_profit_threshold=Decimal("1.5"),
            )
    
    def test_min_greater_than_max_position_size(self):
        """Test that min > max position size raises error."""
        with pytest.raises(ValueError, match="min_position_size.*cannot be greater than max_position_size"):
            Config(
                private_key="0x" + "1" * 64,
                wallet_address=TEST_ADDRESS,
                polygon_rpc_url="https://polygon-rpc.com",
                min_position_size=Decimal("10.0"),
                max_position_size=Decimal("5.0"),
            )
    
    def test_invalid_balance_hierarchy(self):
        """Test that invalid balance hierarchy raises error."""
        with pytest.raises(ValueError, match="target_balance.*must be >= min_balance"):
            Config(
                private_key="0x" + "1" * 64,
                wallet_address=TEST_ADDRESS,
                polygon_rpc_url="https://polygon-rpc.com",
                min_balance=Decimal("100.0"),
                target_balance=Decimal("50.0"),
            )
    
    def test_checksum_address_conversion(self):
        """Test that addresses are converted to checksum format."""
        lowercase_addr = TEST_ADDRESS.lower()
        config = Config(
            private_key="0x" + "1" * 64,
            wallet_address=lowercase_addr,
            polygon_rpc_url="https://polygon-rpc.com",
        )
        
        # Should be converted to checksum (case-insensitive comparison)
        assert config.wallet_address.lower() == lowercase_addr.lower()


class TestConfigLoading:
    """Test configuration loading from different sources."""
    
    def test_load_from_yaml(self):
        """Test loading configuration from YAML file."""
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_data = {
                'private_key': '0x' + '1' * 64,
                'wallet_address': TEST_ADDRESS,
                'polygon_rpc_url': 'https://polygon-rpc.com',
                'stake_amount': '15.0',
                'dry_run': True,
            }
            yaml.dump(yaml_data, f)
            yaml_path = f.name
        
        try:
            config = Config.from_yaml(yaml_path)
            
            assert config.private_key == '0x' + '1' * 64
            assert config.wallet_address.lower() == TEST_ADDRESS.lower()
            assert config.stake_amount == Decimal('15.0')
            assert config.dry_run is True
        finally:
            os.unlink(yaml_path)
    
    def test_load_from_yaml_missing_file(self):
        """Test that loading from missing YAML file raises error."""
        with pytest.raises(FileNotFoundError):
            Config.from_yaml('/nonexistent/config.yaml')
    
    def test_load_from_env(self, monkeypatch):
        """Test loading configuration from environment variables."""
        # Set environment variables
        monkeypatch.setenv('PRIVATE_KEY', '0x' + '2' * 64)
        monkeypatch.setenv('WALLET_ADDRESS', TEST_ADDRESS)
        monkeypatch.setenv('POLYGON_RPC_URL', 'https://polygon-rpc.com')
        monkeypatch.setenv('STAKE_AMOUNT', '20.0')
        monkeypatch.setenv('DRY_RUN', 'true')
        
        config = Config.from_env()
        
        assert config.private_key == '0x' + '2' * 64
        assert config.stake_amount == Decimal('20.0')
        assert config.dry_run is True
    
    def test_backup_rpc_urls_parsing(self, monkeypatch):
        """Test parsing of comma-separated backup RPC URLs."""
        monkeypatch.setenv('PRIVATE_KEY', '0x' + '1' * 64)
        monkeypatch.setenv('WALLET_ADDRESS', TEST_ADDRESS)
        monkeypatch.setenv('POLYGON_RPC_URL', 'https://polygon-rpc.com')
        monkeypatch.setenv('BACKUP_RPC_URLS', 'https://rpc1.com, https://rpc2.com, https://rpc3.com')
        
        config = Config.from_env()
        
        assert len(config.backup_rpc_urls) == 3
        assert 'https://rpc1.com' in config.backup_rpc_urls
        assert 'https://rpc2.com' in config.backup_rpc_urls
        assert 'https://rpc3.com' in config.backup_rpc_urls


class TestConfigToDict:
    """Test configuration serialization."""
    
    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config = Config(
            private_key="0x" + "1" * 64,
            wallet_address=TEST_ADDRESS,
            polygon_rpc_url="https://polygon-rpc.com",
            nvidia_api_key="test_key",
        )
        
        config_dict = config.to_dict()
        
        # Should include wallet address (case-insensitive check)
        assert config_dict['wallet_address'].lower() == TEST_ADDRESS.lower()
        
        # Should not include private key (security)
        assert 'private_key' not in config_dict
        
        # Should indicate API key presence without exposing it
        assert config_dict['has_nvidia_api_key'] is True
        
        # Should include other settings
        assert config_dict['dry_run'] is False
        assert config_dict['stake_amount'] == "10.0"


class TestConfigDefaults:
    """Test default configuration values."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        config = Config(
            private_key="0x" + "1" * 64,
            wallet_address=TEST_ADDRESS,
            polygon_rpc_url="https://polygon-rpc.com",
        )
        
        # Trading parameters
        assert config.stake_amount == Decimal("10.0")
        assert config.min_profit_threshold == Decimal("0.005")
        assert config.max_position_size == Decimal("5.0")
        assert config.min_position_size == Decimal("0.1")
        
        # Risk management
        assert config.max_pending_tx == 5
        assert config.max_gas_price_gwei == 800
        assert config.circuit_breaker_threshold == 10
        
        # Fund management
        assert config.min_balance == Decimal("50.0")
        assert config.target_balance == Decimal("100.0")
        assert config.withdraw_limit == Decimal("500.0")
        
        # Operational
        assert config.dry_run is False
        assert config.scan_interval_seconds == 2
        assert config.heartbeat_interval_seconds == 60
        
        # Chain
        assert config.chain_id == 137


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
