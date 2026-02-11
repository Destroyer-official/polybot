"""
Configuration management for Polymarket Arbitrage Bot.

Supports loading configuration from:
1. Environment variables
2. YAML configuration file
3. Default values

Validates all configuration on startup.
"""

import os
import yaml
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional
from pathlib import Path
from web3 import Web3


@dataclass
class Config:
    """System configuration with validation."""
    
    # Wallet & Keys
    private_key: str
    wallet_address: str
    
    # RPC & APIs
    polygon_rpc_url: str
    backup_rpc_urls: List[str] = field(default_factory=list)
    polymarket_api_url: str = "https://clob.polymarket.com"
    kalshi_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    
    # Contract addresses
    usdc_address: str = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    ctf_exchange_address: str = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    conditional_token_address: str = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    
    # Trading parameters
    stake_amount: Decimal = Decimal("10.0")
    min_profit_threshold: Decimal = Decimal("0.005")  # 0.5%
    max_position_size: Decimal = Decimal("5.0")
    min_position_size: Decimal = Decimal("0.1")
    
    # Risk management
    max_pending_tx: int = 5
    max_gas_price_gwei: int = 800
    circuit_breaker_threshold: int = 10
    
    # Fund management
    min_balance: Decimal = Decimal("50.0")
    target_balance: Decimal = Decimal("100.0")
    withdraw_limit: Decimal = Decimal("500.0")
    
    # Monitoring
    cloudwatch_log_group: str = "/polymarket-arbitrage-bot"
    sns_alert_topic: str = ""
    prometheus_port: int = 9090
    
    # Operational
    dry_run: bool = False
    scan_interval_seconds: int = 2  # Increased from 2 to 5 seconds (more sustainable)
    heartbeat_interval_seconds: int = 60
    
    # Chain ID
    chain_id: int = 137  # Polygon mainnet
    
    # Flash Crash Strategy settings
    flash_crash_drop_threshold: float = 0.20  # 20% drop
    flash_crash_lookback_seconds: int = 10
    flash_crash_trade_size: float = 5.0
    flash_crash_take_profit: float = 0.10
    flash_crash_stop_loss: float = 0.05
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()
        self._convert_to_checksum_addresses()
    
    def _validate(self):
        """Validate all configuration parameters."""
        errors = []
        
        # Validate private key
        if not self.private_key:
            errors.append("private_key is required")
        elif not self.private_key.startswith("0x") and len(self.private_key) != 64:
            if len(self.private_key) != 66:  # 0x + 64 chars
                errors.append("private_key must be 64 hex characters (with or without 0x prefix)")
        
        # Validate wallet address
        if not self.wallet_address:
            errors.append("wallet_address is required")
        elif not Web3.is_address(self.wallet_address):
            errors.append(f"wallet_address is not a valid Ethereum address: {self.wallet_address}")
        
        # Validate RPC URL
        if not self.polygon_rpc_url:
            errors.append("polygon_rpc_url is required")
        elif not self.polygon_rpc_url.startswith(("http://", "https://", "ws://", "wss://")):
            errors.append(f"polygon_rpc_url must be a valid URL: {self.polygon_rpc_url}")
        
        # Validate contract addresses
        for addr_name in ["usdc_address", "ctf_exchange_address", "conditional_token_address"]:
            addr = getattr(self, addr_name)
            if not Web3.is_address(addr):
                errors.append(f"{addr_name} is not a valid Ethereum address: {addr}")
        
        # Validate trading parameters
        if self.stake_amount <= 0:
            errors.append(f"stake_amount must be positive, got: {self.stake_amount}")
        
        if self.min_profit_threshold < 0 or self.min_profit_threshold > 1:
            errors.append(f"min_profit_threshold must be between 0 and 1, got: {self.min_profit_threshold}")
        
        if self.max_position_size <= 0:
            errors.append(f"max_position_size must be positive, got: {self.max_position_size}")
        
        if self.min_position_size <= 0:
            errors.append(f"min_position_size must be positive, got: {self.min_position_size}")
        
        if self.min_position_size > self.max_position_size:
            errors.append(f"min_position_size ({self.min_position_size}) cannot be greater than max_position_size ({self.max_position_size})")
        
        # Validate risk management
        if self.max_pending_tx <= 0:
            errors.append(f"max_pending_tx must be positive, got: {self.max_pending_tx}")
        
        if self.max_gas_price_gwei <= 0:
            errors.append(f"max_gas_price_gwei must be positive, got: {self.max_gas_price_gwei}")
        
        if self.circuit_breaker_threshold <= 0:
            errors.append(f"circuit_breaker_threshold must be positive, got: {self.circuit_breaker_threshold}")
        
        # Validate fund management
        if self.min_balance < 0:
            errors.append(f"min_balance must be non-negative, got: {self.min_balance}")
        
        if self.target_balance < self.min_balance:
            errors.append(f"target_balance ({self.target_balance}) must be >= min_balance ({self.min_balance})")
        
        if self.withdraw_limit < self.target_balance:
            errors.append(f"withdraw_limit ({self.withdraw_limit}) must be >= target_balance ({self.target_balance})")
        
        # Validate operational parameters
        if self.scan_interval_seconds <= 0:
            errors.append(f"scan_interval_seconds must be positive, got: {self.scan_interval_seconds}")
        
        if self.heartbeat_interval_seconds <= 0:
            errors.append(f"heartbeat_interval_seconds must be positive, got: {self.heartbeat_interval_seconds}")
        
        if self.prometheus_port <= 0 or self.prometheus_port > 65535:
            errors.append(f"prometheus_port must be between 1 and 65535, got: {self.prometheus_port}")
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)
    
    def _convert_to_checksum_addresses(self):
        """Convert all addresses to checksum format."""
        self.wallet_address = Web3.to_checksum_address(self.wallet_address)
        self.usdc_address = Web3.to_checksum_address(self.usdc_address)
        self.ctf_exchange_address = Web3.to_checksum_address(self.ctf_exchange_address)
        self.conditional_token_address = Web3.to_checksum_address(self.conditional_token_address)
    
    @classmethod
    def from_env(cls, use_aws_secrets: bool = False, secret_name: str = "polymarket-bot-credentials") -> "Config":
        """
        Load configuration from environment variables or AWS Secrets Manager.
        
        Args:
            use_aws_secrets: If True, retrieve private key from AWS Secrets Manager
            secret_name: Name of the secret in AWS Secrets Manager
        """
        from dotenv import load_dotenv
        load_dotenv()
        
        # Retrieve secrets (private key, API keys) from AWS or environment
        if use_aws_secrets:
            try:
                from src.secrets_manager import get_secrets_manager
                secrets_mgr = get_secrets_manager(use_aws=True)
                secret_data = secrets_mgr.get_secret(secret_name)
                
                private_key = secret_data.get('private_key', '')
                wallet_address = secret_data.get('wallet_address', os.getenv("WALLET_ADDRESS", ""))
                nvidia_api_key = secret_data.get('nvidia_api_key', os.getenv("NVIDIA_API_KEY"))
                kalshi_api_key = secret_data.get('kalshi_api_key', os.getenv("KALSHI_API_KEY"))
            except Exception as e:
                import logging
                logging.warning(f"Failed to retrieve secrets from AWS: {e}. Falling back to environment variables.")
                private_key = os.getenv("PRIVATE_KEY", "")
                wallet_address = os.getenv("WALLET_ADDRESS", "")
                nvidia_api_key = os.getenv("NVIDIA_API_KEY")
                kalshi_api_key = os.getenv("KALSHI_API_KEY")
        else:
            private_key = os.getenv("PRIVATE_KEY", "")
            wallet_address = os.getenv("WALLET_ADDRESS", "")
            nvidia_api_key = os.getenv("NVIDIA_API_KEY")
            kalshi_api_key = os.getenv("KALSHI_API_KEY")
        
        # Parse backup RPC URLs
        backup_rpcs = os.getenv("BACKUP_RPC_URLS", "")
        backup_rpc_list = [url.strip() for url in backup_rpcs.split(",") if url.strip()]
        
        return cls(
            # Wallet & Keys
            private_key=private_key,
            wallet_address=wallet_address,
            
            # RPC & APIs
            polygon_rpc_url=os.getenv("POLYGON_RPC_URL", os.getenv("RPC_URL", "https://polygon-rpc.com")),
            backup_rpc_urls=backup_rpc_list,
            polymarket_api_url=os.getenv("POLYMARKET_API_URL", "https://clob.polymarket.com"),
            kalshi_api_key=kalshi_api_key,
            nvidia_api_key=nvidia_api_key,
            
            # Contract addresses
            usdc_address=os.getenv("USDC_ADDRESS", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"),
            ctf_exchange_address=os.getenv("CTF_EXCHANGE_ADDRESS", "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"),
            conditional_token_address=os.getenv("CONDITIONAL_TOKEN_ADDRESS", "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"),
            
            # Trading parameters
            stake_amount=Decimal(os.getenv("STAKE_AMOUNT", "10.0")),
            min_profit_threshold=Decimal(os.getenv("MIN_PROFIT_THRESHOLD", "0.005")),
            max_position_size=Decimal(os.getenv("MAX_POSITION_SIZE", "5.0")),
            min_position_size=Decimal(os.getenv("MIN_POSITION_SIZE", "0.1")),
            
            # Risk management
            max_pending_tx=int(os.getenv("MAX_PENDING_TX", "5")),
            max_gas_price_gwei=int(os.getenv("MAX_GAS_PRICE_GWEI", "800")),
            circuit_breaker_threshold=int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "10")),
            
            # Fund management
            min_balance=Decimal(os.getenv("MIN_BALANCE", "50.0")),
            target_balance=Decimal(os.getenv("TARGET_BALANCE", "100.0")),
            withdraw_limit=Decimal(os.getenv("WITHDRAW_LIMIT", "500.0")),
            
            # Monitoring
            cloudwatch_log_group=os.getenv("CLOUDWATCH_LOG_GROUP", "/polymarket-arbitrage-bot"),
            sns_alert_topic=os.getenv("SNS_ALERT_TOPIC", ""),
            prometheus_port=int(os.getenv("PROMETHEUS_PORT", "9090")),
            
            # Operational
            dry_run=os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes"),
            scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "2")),  # Increased default from 2 to 5
            heartbeat_interval_seconds=int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "60")),
            
            # Chain ID
            chain_id=int(os.getenv("CHAIN_ID", "137")),
            
            # Flash Crash Strategy
            flash_crash_drop_threshold=float(os.getenv("FLASH_CRASH_DROP_THRESHOLD", "0.20")),
            flash_crash_lookback_seconds=int(os.getenv("FLASH_CRASH_LOOKBACK_SECONDS", "10")),
            flash_crash_trade_size=float(os.getenv("FLASH_CRASH_TRADE_SIZE", "5.0")),
            flash_crash_take_profit=float(os.getenv("FLASH_CRASH_TAKE_PROFIT", "0.10")),
            flash_crash_stop_loss=float(os.getenv("FLASH_CRASH_STOP_LOSS", "0.05")),
        )
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Config":
        """Load configuration from YAML file."""
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {yaml_path}")
        
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        if not data:
            raise ValueError(f"Empty configuration file: {yaml_path}")
        
        # Convert string decimals to Decimal objects
        for key in ["stake_amount", "min_profit_threshold", "max_position_size", 
                    "min_position_size", "min_balance", "target_balance", "withdraw_limit"]:
            if key in data:
                data[key] = Decimal(str(data[key]))
        
        return cls(**data)
    
    @classmethod
    def load(cls, yaml_path: Optional[str] = None, use_aws_secrets: bool = False, 
             secret_name: str = "polymarket-bot-credentials") -> "Config":
        """
        Load configuration with priority:
        1. YAML file (if provided)
        2. AWS Secrets Manager (if use_aws_secrets=True)
        3. Environment variables
        4. Default values
        
        Args:
            yaml_path: Optional path to YAML configuration file
            use_aws_secrets: If True, retrieve secrets from AWS Secrets Manager
            secret_name: Name of the secret in AWS Secrets Manager
        """
        if yaml_path:
            return cls.from_yaml(yaml_path)
        else:
            return cls.from_env(use_aws_secrets=use_aws_secrets, secret_name=secret_name)
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary (for logging)."""
        config_dict = {
            "wallet_address": self.wallet_address,
            "polygon_rpc_url": self.polygon_rpc_url,
            "backup_rpc_urls": self.backup_rpc_urls,
            "polymarket_api_url": self.polymarket_api_url,
            "has_kalshi_api_key": bool(self.kalshi_api_key),
            "has_nvidia_api_key": bool(self.nvidia_api_key),
            "usdc_address": self.usdc_address,
            "ctf_exchange_address": self.ctf_exchange_address,
            "conditional_token_address": self.conditional_token_address,
            "stake_amount": str(self.stake_amount),
            "min_profit_threshold": str(self.min_profit_threshold),
            "max_position_size": str(self.max_position_size),
            "min_position_size": str(self.min_position_size),
            "max_pending_tx": self.max_pending_tx,
            "max_gas_price_gwei": self.max_gas_price_gwei,
            "circuit_breaker_threshold": self.circuit_breaker_threshold,
            "min_balance": str(self.min_balance),
            "target_balance": str(self.target_balance),
            "withdraw_limit": str(self.withdraw_limit),
            "cloudwatch_log_group": self.cloudwatch_log_group,
            "sns_alert_topic": self.sns_alert_topic,
            "prometheus_port": self.prometheus_port,
            "dry_run": self.dry_run,
            "scan_interval_seconds": self.scan_interval_seconds,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "chain_id": self.chain_id,
        }
        return config_dict


def load_config(yaml_path: Optional[str] = None, use_aws_secrets: bool = False,
                secret_name: str = "polymarket-bot-credentials") -> Config:
    """
    Convenience function to load and validate configuration.
    
    Args:
        yaml_path: Optional path to YAML configuration file
        use_aws_secrets: If True, retrieve secrets from AWS Secrets Manager
        secret_name: Name of the secret in AWS Secrets Manager
        
    Returns:
        Validated Config object
        
    Raises:
        ValueError: If configuration is invalid
        FileNotFoundError: If YAML file not found
    """
    return Config.load(yaml_path=yaml_path, use_aws_secrets=use_aws_secrets, secret_name=secret_name)
