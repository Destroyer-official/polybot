"""
Property-based tests for security features.

Tests:
- Property 41: Private Key Logging Prevention (Requirement 14.3)
- Property 42: Wallet Address Verification (Requirement 14.4)
"""

import pytest
import logging
import io
from hypothesis import given, strategies as st, settings
from web3 import Web3
from eth_account import Account

from src.secrets_manager import SecretsManager, SecureLogger
from src.wallet_verifier import WalletVerifier


# ============================================================================
# Property 41: Private Key Logging Prevention
# ============================================================================
# **Validates: Requirements 14.3**
#
# **Property Statement:**
# For any valid private key and any log message containing that private key,
# the sanitize_log_message function MUST redact the private key from the message.
#
# **Formal Specification:**
# ∀ private_key ∈ ValidPrivateKeys, ∀ message ∈ Strings:
#   private_key ∈ message ⟹ private_key ∉ sanitize_log_message(message)
#
# **Test Strategy:**
# 1. Generate random valid private keys (64 hex characters)
# 2. Embed private keys in various log message formats
# 3. Verify sanitize_log_message removes all occurrences
# 4. Test with and without 0x prefix
# 5. Test with multiple private keys in same message
# 6. Test with private keys in different positions
# ============================================================================

@given(
    private_key=st.text(
        alphabet='0123456789abcdefABCDEF',
        min_size=64,
        max_size=64
    ),
    prefix=st.sampled_from(['0x', '0X', '']),
    message_template=st.sampled_from([
        'Private key: {}',
        'Using key {} for authentication',
        'Error with key: {}',
        'Key={} failed',
        'Debug: private_key={}, wallet=0x123',
        'Multiple keys: {} and {}',
        '{} is the private key',
        'Start {} middle {} end',
    ])
)
@settings(max_examples=100)
def test_property_41_private_key_logging_prevention(private_key, prefix, message_template):
    """
    Property 41: Private Key Logging Prevention
    
    Validates: Requirements 14.3
    
    Tests that private keys are always redacted from log messages,
    regardless of format or position in the message.
    """
    # Construct full private key with optional prefix
    full_key = prefix + private_key
    
    # Create message containing the private key
    if '{}' in message_template:
        # Handle templates with multiple placeholders
        placeholders_count = message_template.count('{}')
        if placeholders_count == 1:
            message = message_template.format(full_key)
        else:
            # Fill all placeholders with the same key for simplicity
            message = message_template.format(*([full_key] * placeholders_count))
    else:
        message = message_template + full_key
    
    # Sanitize the message
    sanitized = SecretsManager.sanitize_log_message(message)
    
    # PROPERTY: Private key must not appear in sanitized message
    # Check both with and without prefix
    assert private_key.lower() not in sanitized.lower(), \
        f"Private key found in sanitized message: {sanitized}"
    
    if prefix:
        assert full_key.lower() not in sanitized.lower(), \
            f"Private key with prefix found in sanitized message: {sanitized}"
    
    # PROPERTY: Sanitized message should contain redaction marker
    assert '[REDACTED_PRIVATE_KEY]' in sanitized, \
        f"Redaction marker not found in sanitized message: {sanitized}"


def test_property_41_secure_logger_never_logs_private_keys():
    """
    Property 41: Secure Logger Never Logs Private Keys
    
    Validates: Requirements 14.3
    
    Tests that SecureLogger wrapper automatically sanitizes all log messages.
    """
    # Create a test private key
    account = Account.create()
    private_key = account.key.hex()
    
    # Setup in-memory log handler to capture logs
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)
    
    # Create logger and secure wrapper
    test_logger = logging.getLogger('test_secure_logger')
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(handler)
    
    secure_logger = SecureLogger(test_logger)
    
    # Log messages containing private key at different levels
    secure_logger.debug(f"Debug: private_key={private_key}")
    secure_logger.info(f"Info: Using key {private_key}")
    secure_logger.warning(f"Warning: Key {private_key} failed")
    secure_logger.error(f"Error: {private_key}")
    secure_logger.critical(f"Critical: private_key={private_key}")
    
    # Get logged content
    log_content = log_stream.getvalue()
    
    # PROPERTY: Private key must never appear in logs
    assert private_key not in log_content, \
        f"Private key found in logs: {log_content}"
    
    # PROPERTY: All messages should contain redaction marker
    assert log_content.count('[REDACTED_PRIVATE_KEY]') == 5, \
        f"Expected 5 redaction markers, found {log_content.count('[REDACTED_PRIVATE_KEY]')}"
    
    # Cleanup
    test_logger.removeHandler(handler)


@given(
    num_keys=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=50)
def test_property_41_multiple_private_keys_redacted(num_keys):
    """
    Property 41: Multiple Private Keys Redacted
    
    Validates: Requirements 14.3
    
    Tests that multiple private keys in the same message are all redacted.
    """
    # Generate multiple private keys
    private_keys = [Account.create().key.hex() for _ in range(num_keys)]
    
    # Create message with all keys
    message = "Keys: " + ", ".join(private_keys)
    
    # Sanitize
    sanitized = SecretsManager.sanitize_log_message(message)
    
    # PROPERTY: None of the private keys should appear in sanitized message
    for key in private_keys:
        assert key not in sanitized, \
            f"Private key {key} found in sanitized message"
    
    # PROPERTY: Should have correct number of redaction markers
    assert sanitized.count('[REDACTED_PRIVATE_KEY]') == num_keys, \
        f"Expected {num_keys} redaction markers, found {sanitized.count('[REDACTED_PRIVATE_KEY]')}"


def test_property_41_edge_cases():
    """
    Property 41: Edge Cases for Private Key Redaction
    
    Validates: Requirements 14.3
    
    Tests edge cases like partial keys, invalid keys, etc.
    """
    # Test 1: Partial private key (should not be redacted)
    partial_key = "0x" + "a" * 32  # Only 32 hex chars, not 64
    message = f"Partial key: {partial_key}"
    sanitized = SecretsManager.sanitize_log_message(message)
    assert partial_key in sanitized, "Partial key should not be redacted"
    
    # Test 2: Valid private key without 0x prefix
    valid_key = "a" * 64
    message = f"Key: {valid_key}"
    sanitized = SecretsManager.sanitize_log_message(message)
    assert valid_key not in sanitized, "Valid key without prefix should be redacted"
    assert '[REDACTED_PRIVATE_KEY]' in sanitized
    
    # Test 3: Valid private key with 0x prefix
    valid_key_with_prefix = "0x" + "b" * 64
    message = f"Key: {valid_key_with_prefix}"
    sanitized = SecretsManager.sanitize_log_message(message)
    assert valid_key_with_prefix not in sanitized, "Valid key with prefix should be redacted"
    assert '[REDACTED_PRIVATE_KEY]' in sanitized
    
    # Test 4: Message with no private keys
    message = "This is a normal log message with no keys"
    sanitized = SecretsManager.sanitize_log_message(message)
    assert sanitized == message, "Message without keys should be unchanged"
    assert '[REDACTED_PRIVATE_KEY]' not in sanitized
    
    # Test 5: Empty message
    message = ""
    sanitized = SecretsManager.sanitize_log_message(message)
    assert sanitized == "", "Empty message should remain empty"


# ============================================================================
# Property 42: Wallet Address Verification
# ============================================================================
# **Validates: Requirements 14.4**
#
# **Property Statement:**
# For any valid private key, the derived wallet address MUST match the address
# derived by the Ethereum standard (secp256k1 elliptic curve cryptography).
# Verification MUST fail if the expected address does not match the derived address.
#
# **Formal Specification:**
# ∀ private_key ∈ ValidPrivateKeys:
#   verify_wallet_address(private_key, derive_address(private_key)) = True
#   ∀ wrong_address ≠ derive_address(private_key):
#     verify_wallet_address(private_key, wrong_address) = False
#
# **Test Strategy:**
# 1. Generate random private keys
# 2. Derive correct address from private key
# 3. Verify that verification succeeds with correct address
# 4. Verify that verification fails with incorrect address
# 5. Test with various address formats (checksum, lowercase, uppercase)
# ============================================================================

# Maximum valid private key for secp256k1 curve
# This is the order of the curve (n)
SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

@given(
    seed=st.integers(min_value=1, max_value=SECP256K1_N - 1)
)
@settings(max_examples=100)
def test_property_42_wallet_address_verification_correct_address(seed):
    """
    Property 42: Wallet Address Verification - Correct Address
    
    Validates: Requirements 14.4
    
    Tests that verification succeeds when private key matches expected address.
    """
    # Generate account from seed
    private_key = hex(seed)[2:].zfill(64)
    account = Account.from_key('0x' + private_key)
    expected_address = account.address
    
    # PROPERTY: Verification must succeed with correct address
    result = WalletVerifier.verify_wallet_address('0x' + private_key, expected_address)
    assert result is True, \
        f"Verification failed for correct address. Key: {private_key}, Address: {expected_address}"


@given(
    seed=st.integers(min_value=1, max_value=SECP256K1_N - 1)
)
@settings(max_examples=100)
def test_property_42_wallet_address_verification_wrong_address(seed):
    """
    Property 42: Wallet Address Verification - Wrong Address
    
    Validates: Requirements 14.4
    
    Tests that verification fails when private key doesn't match expected address.
    """
    # Generate account from seed
    private_key = hex(seed)[2:].zfill(64)
    account = Account.from_key('0x' + private_key)
    correct_address = account.address
    
    # Generate a different address
    wrong_account = Account.create()
    wrong_address = wrong_account.address
    
    # Ensure addresses are different
    if correct_address.lower() == wrong_address.lower():
        # Skip this test case if by chance we generated the same address
        return
    
    # PROPERTY: Verification must fail with wrong address
    result = WalletVerifier.verify_wallet_address('0x' + private_key, wrong_address)
    assert result is False, \
        f"Verification succeeded with wrong address. Key: {private_key}, Wrong: {wrong_address}, Correct: {correct_address}"


def test_property_42_address_format_normalization():
    """
    Property 42: Address Format Normalization
    
    Validates: Requirements 14.4
    
    Tests that verification works with different address formats
    (checksum, lowercase, uppercase).
    """
    # Create test account
    account = Account.create()
    private_key = account.key.hex()
    address = account.address
    
    # Test with checksum address
    result = WalletVerifier.verify_wallet_address(private_key, address)
    assert result is True, "Verification failed with checksum address"
    
    # Test with lowercase address
    result = WalletVerifier.verify_wallet_address(private_key, address.lower())
    assert result is True, "Verification failed with lowercase address"
    
    # Test with uppercase address (without 0x)
    result = WalletVerifier.verify_wallet_address(private_key, address.upper())
    assert result is True, "Verification failed with uppercase address"


def test_property_42_private_key_format_variations():
    """
    Property 42: Private Key Format Variations
    
    Validates: Requirements 14.4
    
    Tests that verification works with private keys with or without 0x prefix.
    """
    # Create test account
    account = Account.create()
    private_key_with_prefix = account.key.hex()
    private_key_without_prefix = private_key_with_prefix.replace('0x', '')
    address = account.address
    
    # Test with 0x prefix
    result = WalletVerifier.verify_wallet_address(private_key_with_prefix, address)
    assert result is True, "Verification failed with 0x prefix"
    
    # Test without 0x prefix
    result = WalletVerifier.verify_wallet_address(private_key_without_prefix, address)
    assert result is True, "Verification failed without 0x prefix"


def test_property_42_derive_address_consistency():
    """
    Property 42: Derive Address Consistency
    
    Validates: Requirements 14.4
    
    Tests that deriving an address from a private key is consistent
    with Web3's derivation.
    """
    # Create test account
    account = Account.create()
    private_key = account.key.hex()
    expected_address = account.address
    
    # Derive address using WalletVerifier
    derived_address = WalletVerifier.derive_address_from_private_key(private_key)
    
    # PROPERTY: Derived address must match Web3's derivation
    assert Web3.to_checksum_address(derived_address) == Web3.to_checksum_address(expected_address), \
        f"Derived address mismatch. Expected: {expected_address}, Got: {derived_address}"


def test_property_42_invalid_private_key_handling():
    """
    Property 42: Invalid Private Key Handling
    
    Validates: Requirements 14.4
    
    Tests that verification properly handles invalid private keys.
    """
    invalid_keys = [
        "",  # Empty
        "0x",  # Only prefix
        "0x123",  # Too short
        "not_a_hex_string" * 8,  # Invalid characters
        "0x" + "g" * 64,  # Invalid hex characters
    ]
    
    for invalid_key in invalid_keys:
        with pytest.raises(ValueError):
            WalletVerifier.verify_wallet_address(invalid_key, "0x" + "0" * 40)


def test_property_42_invalid_address_handling():
    """
    Property 42: Invalid Address Handling
    
    Validates: Requirements 14.4
    
    Tests that verification properly handles invalid addresses.
    """
    # Create valid private key
    account = Account.create()
    private_key = account.key.hex()
    
    invalid_addresses = [
        "",  # Empty
        "0x",  # Only prefix
        "0x123",  # Too short
        "not_an_address",  # Invalid format
        "0x" + "g" * 40,  # Invalid hex characters
    ]
    
    for invalid_address in invalid_addresses:
        with pytest.raises(ValueError):
            WalletVerifier.verify_wallet_address(private_key, invalid_address)


def test_property_42_verify_or_derive_with_expected_address():
    """
    Property 42: Verify or Derive with Expected Address
    
    Validates: Requirements 14.4
    
    Tests verify_or_derive_address when expected address is provided.
    """
    # Create test account
    account = Account.create()
    private_key = account.key.hex()
    correct_address = account.address
    
    # Should succeed with correct address
    result = WalletVerifier.verify_or_derive_address(private_key, correct_address)
    assert Web3.to_checksum_address(result) == Web3.to_checksum_address(correct_address)
    
    # Should fail with wrong address
    wrong_address = Account.create().address
    if correct_address.lower() != wrong_address.lower():
        with pytest.raises(ValueError):
            WalletVerifier.verify_or_derive_address(private_key, wrong_address)


def test_property_42_verify_or_derive_without_expected_address():
    """
    Property 42: Verify or Derive without Expected Address
    
    Validates: Requirements 14.4
    
    Tests verify_or_derive_address when no expected address is provided.
    """
    # Create test account
    account = Account.create()
    private_key = account.key.hex()
    expected_address = account.address
    
    # Should derive address when none provided
    result = WalletVerifier.verify_or_derive_address(private_key, None)
    assert Web3.to_checksum_address(result) == Web3.to_checksum_address(expected_address)
