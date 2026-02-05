"""
AWS Secrets Manager integration for secure private key storage.

Implements Requirements 14.1, 14.3:
- Retrieve private keys from AWS Secrets Manager
- Use IAM roles for authentication
- Never log private keys
"""

import json
import logging
from typing import Dict, Any, Optional
import re

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Manages secure retrieval of secrets from AWS Secrets Manager.
    
    Responsibilities:
    - Retrieve private keys from AWS Secrets Manager
    - Use IAM roles for authentication (no hardcoded credentials)
    - Ensure private keys are never logged
    - Provide fallback to environment variables for local development
    
    Validates Requirements:
    - 14.1: Retrieve private keys from Secrets Manager
    - 14.3: Never log private keys
    """
    
    def __init__(self, use_aws: bool = True, region_name: str = "us-east-1"):
        """
        Initialize Secrets Manager client.
        
        Args:
            use_aws: If True, use AWS Secrets Manager. If False, use environment variables.
            region_name: AWS region for Secrets Manager
        """
        self.use_aws = use_aws
        self.region_name = region_name
        self._client = None
        
        if use_aws:
            try:
                import boto3
                # Use IAM role credentials (no explicit credentials needed)
                self._client = boto3.client('secretsmanager', region_name=region_name)
                logger.info(f"AWS Secrets Manager client initialized (region: {region_name})")
            except ImportError:
                logger.warning("boto3 not installed. Falling back to environment variables.")
                self.use_aws = False
            except Exception as e:
                logger.warning(f"Failed to initialize AWS Secrets Manager: {e}. Falling back to environment variables.")
                self.use_aws = False
    
    def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """
        Retrieve a secret from AWS Secrets Manager or environment variables.
        
        Args:
            secret_name: Name of the secret in AWS Secrets Manager
            
        Returns:
            Dictionary containing secret values
            
        Raises:
            ValueError: If secret cannot be retrieved
        """
        if self.use_aws:
            return self._get_secret_from_aws(secret_name)
        else:
            return self._get_secret_from_env()
    
    def _get_secret_from_aws(self, secret_name: str) -> Dict[str, Any]:
        """
        Retrieve secret from AWS Secrets Manager.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Dictionary containing secret values
            
        Raises:
            ValueError: If secret cannot be retrieved
        """
        try:
            logger.info(f"Retrieving secret from AWS Secrets Manager: {secret_name}")
            
            response = self._client.get_secret_value(SecretId=secret_name)
            
            # Parse secret string
            if 'SecretString' in response:
                secret_data = json.loads(response['SecretString'])
            else:
                # Binary secrets not supported for this use case
                raise ValueError("Binary secrets are not supported")
            
            # Validate required fields
            if 'private_key' not in secret_data:
                raise ValueError("Secret must contain 'private_key' field")
            
            # CRITICAL: Never log the actual private key
            logger.info("Secret retrieved successfully from AWS Secrets Manager")
            logger.debug(f"Secret contains keys: {list(secret_data.keys())}")
            
            return secret_data
            
        except Exception as e:
            logger.error(f"Failed to retrieve secret from AWS: {e}")
            raise ValueError(f"Failed to retrieve secret '{secret_name}': {e}")
    
    def _get_secret_from_env(self) -> Dict[str, Any]:
        """
        Retrieve secret from environment variables (fallback for local development).
        
        Returns:
            Dictionary containing secret values from environment
            
        Raises:
            ValueError: If required environment variables are missing
        """
        import os
        
        logger.info("Retrieving credentials from environment variables")
        
        private_key = os.getenv("PRIVATE_KEY")
        if not private_key:
            raise ValueError("PRIVATE_KEY environment variable is required")
        
        # CRITICAL: Never log the actual private key
        logger.info("Credentials retrieved from environment variables")
        
        secret_data = {
            'private_key': private_key,
            'wallet_address': os.getenv("WALLET_ADDRESS", ""),
        }
        
        # Add optional fields if present
        if os.getenv("NVIDIA_API_KEY"):
            secret_data['nvidia_api_key'] = os.getenv("NVIDIA_API_KEY")
        if os.getenv("KALSHI_API_KEY"):
            secret_data['kalshi_api_key'] = os.getenv("KALSHI_API_KEY")
        
        return secret_data
    
    def get_private_key(self, secret_name: str = "polymarket-bot-credentials") -> str:
        """
        Retrieve private key from AWS Secrets Manager.
        
        Args:
            secret_name: Name of the secret containing the private key
            
        Returns:
            Private key string
            
        Raises:
            ValueError: If private key cannot be retrieved
        """
        secret_data = self.get_secret(secret_name)
        private_key = secret_data.get('private_key')
        
        if not private_key:
            raise ValueError("Private key not found in secret")
        
        # Validate private key format (without logging it)
        if not self._is_valid_private_key_format(private_key):
            raise ValueError("Invalid private key format")
        
        # CRITICAL: Never log the private key
        logger.info("Private key retrieved and validated")
        
        return private_key
    
    def _is_valid_private_key_format(self, private_key: str) -> bool:
        """
        Validate private key format without logging it.
        
        Args:
            private_key: Private key to validate
            
        Returns:
            True if format is valid, False otherwise
        """
        # Remove 0x prefix if present
        key = private_key.replace('0x', '').replace('0X', '')
        
        # Check if it's 64 hex characters
        if len(key) != 64:
            return False
        
        # Check if all characters are hex
        try:
            int(key, 16)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def sanitize_log_message(message: str) -> str:
        """
        Sanitize log messages to remove any potential private keys.
        
        This is a safety measure to prevent accidental logging of private keys.
        
        Args:
            message: Log message to sanitize
            
        Returns:
            Sanitized message with private keys redacted
        """
        # Pattern to match potential private keys (64 hex characters, optionally prefixed with 0x or 0X)
        pattern = r'\b(?:0[xX])?[0-9a-fA-F]{64}\b'
        
        # Replace with redacted marker
        sanitized = re.sub(pattern, '[REDACTED_PRIVATE_KEY]', message)
        
        return sanitized


class SecureLogger:
    """
    Logging wrapper that automatically sanitizes private keys from log messages.
    
    Validates Requirement 14.3: Never log private keys
    """
    
    def __init__(self, logger_instance: logging.Logger):
        """
        Initialize secure logger wrapper.
        
        Args:
            logger_instance: Standard Python logger to wrap
        """
        self._logger = logger_instance
    
    def _sanitize(self, message: str) -> str:
        """Sanitize message to remove private keys."""
        return SecretsManager.sanitize_log_message(str(message))
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message with sanitization."""
        self._logger.debug(self._sanitize(message), *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message with sanitization."""
        self._logger.info(self._sanitize(message), *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message with sanitization."""
        self._logger.warning(self._sanitize(message), *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message with sanitization."""
        self._logger.error(self._sanitize(message), *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message with sanitization."""
        self._logger.critical(self._sanitize(message), *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        """Log exception with sanitization."""
        self._logger.exception(self._sanitize(message), *args, **kwargs)


def get_secrets_manager(use_aws: bool = True, region_name: str = "us-east-1") -> SecretsManager:
    """
    Factory function to create SecretsManager instance.
    
    Args:
        use_aws: If True, use AWS Secrets Manager. If False, use environment variables.
        region_name: AWS region for Secrets Manager
        
    Returns:
        SecretsManager instance
    """
    return SecretsManager(use_aws=use_aws, region_name=region_name)
