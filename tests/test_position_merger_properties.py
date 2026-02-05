"""
Property-based tests for Position Merger.

Tests merge redemption invariant.
Validates Requirement 1.6.
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.position_merger import (
    PositionMerger,
    PositionMergerError,
    InsufficientBalanceError,
    MergeRedemptionError
)


# Mock Web3 and Contract for testing
class MockWeb3:
    """Mock Web3 instance for testing."""
    
    def __init__(self):
        self.eth = MockEth()
    
    @staticmethod
    def to_checksum_address(address):
        """Mock checksum address conversion - just return the address."""
        # Simple mock: just return the address as-is if it's valid format
        if isinstance(address, str) and address.startswith('0x') and len(address) == 42:
            return address
        return address


class MockEth:
    """Mock eth interface."""
    
    def __init__(self):
        self.gas_price = 50_000_000_000  # 50 gwei
        self._nonce = 0
        self._tx_counter = 0
        self._receipts = {}
        self._usdc_contract = None  # Will be set by test
        self._merge_amount = None  # Will be set when merge is called
        self._wallet_address = None
    
    def get_transaction_count(self, address, block='latest'):
        """Mock get_transaction_count."""
        return self._nonce
    
    def send_raw_transaction(self, raw_tx):
        """Mock send_raw_transaction."""
        self._tx_counter += 1
        tx_hash = f"0x{self._tx_counter:064x}"
        return bytes.fromhex(tx_hash[2:])
    
    def wait_for_transaction_receipt(self, tx_hash, timeout=120):
        """Mock wait_for_transaction_receipt."""
        tx_hash_hex = tx_hash.hex() if isinstance(tx_hash, bytes) else tx_hash
        
        # Simulate the merge: increase USDC balance by merge amount
        if self._usdc_contract and self._merge_amount and self._wallet_address:
            current_balance = self._usdc_contract.functions._usdc_balances.get(
                self._wallet_address, 0
            )
            new_balance = current_balance + self._merge_amount
            self._usdc_contract.functions._usdc_balances[self._wallet_address] = new_balance
        
        return {
            'transactionHash': tx_hash_hex,
            'status': 1,
            'blockNumber': 12345,
            'gasUsed': 100000
        }
    
    def contract(self, address, abi):
        """Mock contract creation."""
        return MockContract(address, abi, self)


class MockContract:
    """Mock contract for testing."""
    
    def __init__(self, address, abi, eth=None):
        self.address = address
        self.abi = abi
        self.eth = eth
        self.functions = MockContractFunctions(address, eth)


class MockContractFunctions:
    """Mock contract functions."""
    
    def __init__(self, address, eth=None):
        self.address = address
        self.eth = eth
        # Track balances: {(owner, token_id): balance_wei}
        self._position_balances = {}
        # Track USDC balances: {owner: balance_wei}
        self._usdc_balances = {}
    
    def set_position_balance(self, owner, token_id, balance_wei):
        """Set position balance for testing."""
        self._position_balances[(owner, token_id)] = balance_wei
    
    def set_usdc_balance(self, owner, balance_wei):
        """Set USDC balance for testing."""
        self._usdc_balances[owner] = balance_wei
    
    def balanceOf(self, owner, token_id=None):
        """Mock balanceOf function."""
        if token_id is not None:
            # CTF position balance
            balance = self._position_balances.get((owner, token_id), 0)
            return MockCall(balance)
        else:
            # USDC balance
            balance = self._usdc_balances.get(owner, 0)
            return MockCall(balance)
    
    def mergePositions(self, collateral_token, parent_collection_id, 
                      condition_id, partition, amount):
        """Mock mergePositions function."""
        return MockMergeFunction(
            self, self.eth, collateral_token, parent_collection_id,
            condition_id, partition, amount
        )


class MockCall:
    """Mock contract call result."""
    
    def __init__(self, return_value):
        self.return_value = return_value
    
    def call(self):
        """Execute mock call."""
        return self.return_value


class MockMergeFunction:
    """Mock merge function for building and estimating."""
    
    def __init__(self, functions, eth, collateral_token, parent_collection_id,
                 condition_id, partition, amount):
        self.functions = functions
        self.eth = eth
        self.collateral_token = collateral_token
        self.parent_collection_id = parent_collection_id
        self.condition_id = condition_id
        self.partition = partition
        self.amount = amount
    
    def estimate_gas(self, tx_params):
        """Mock gas estimation."""
        return 200000
    
    def build_transaction(self, tx_params):
        """Mock transaction building."""
        # Store merge amount in eth for simulation
        if self.eth:
            self.eth._merge_amount = self.amount
            self.eth._wallet_address = tx_params['from']
        
        return {
            'from': tx_params['from'],
            'gas': tx_params.get('gas', 200000),
            'gasPrice': tx_params.get('gasPrice', 50_000_000_000),
            'nonce': tx_params.get('nonce', 0),
            'to': self.functions.address,
            'data': '0x' + '0' * 64
        }


class MockAccount:
    """Mock account for testing."""
    
    def __init__(self, address="0x1234567890123456789012345678901234567890"):
        self.address = address
    
    def sign_transaction(self, tx_params):
        """Mock sign_transaction."""
        mock_signed = Mock()
        mock_signed.raw_transaction = b'\x00' * 32
        return mock_signed


@given(
    merge_amount=st.decimals(
        min_value='0.1',
        max_value='100.0',
        places=2
    ),
    yes_balance_multiplier=st.decimals(
        min_value='1.0',
        max_value='10.0',
        places=2
    ),
    no_balance_multiplier=st.decimals(
        min_value='1.0',
        max_value='10.0',
        places=2
    ),
    initial_usdc=st.decimals(
        min_value='0.0',
        max_value='10000.0',
        places=2
    )
)
@settings(max_examples=100, deadline=None)
def test_merge_redemption_invariant(
    merge_amount,
    yes_balance_multiplier,
    no_balance_multiplier,
    initial_usdc
):
    """
    **Validates: Requirement 1.6**
    
    Feature: polymarket-arbitrage-bot, Property 4: Position Merge Redemption Invariant
    
    For any successful merge of N YES and N NO positions, the wallet should receive
    exactly N * $1.00 USDC. This is a mathematical invariant that must hold for all
    valid merges.
    
    This test verifies:
    1. USDC balance increases by exactly merge_amount after merge
    2. The redemption is exactly $1.00 per position pair
    3. The invariant holds regardless of initial balances
    4. The invariant holds for any merge amount
    """
    # Setup
    web3 = MockWeb3()
    wallet = MockAccount()
    
    ctf_address = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    
    position_merger = PositionMerger(
        web3=web3,
        ctf_contract_address=ctf_address,
        usdc_address=usdc_address,
        wallet=wallet
    )
    
    # Setup test data
    condition_id = "0x" + "c" * 64
    yes_token_id = "0x" + "1" * 64
    no_token_id = "0x" + "2" * 64
    
    # Set position balances (ensure sufficient for merge)
    yes_balance = merge_amount * yes_balance_multiplier
    no_balance = merge_amount * no_balance_multiplier
    
    yes_balance_wei = int(yes_balance * Decimal(10 ** 6))
    no_balance_wei = int(no_balance * Decimal(10 ** 6))
    initial_usdc_wei = int(initial_usdc * Decimal(10 ** 6))
    
    # Configure mock balances
    ctf_contract = position_merger.ctf_contract
    usdc_contract = position_merger.usdc_contract
    
    # Link USDC contract to eth mock for balance simulation
    web3.eth._usdc_contract = usdc_contract
    
    # Set initial position balances
    ctf_contract.functions.set_position_balance(
        wallet.address, int(yes_token_id, 16), yes_balance_wei
    )
    ctf_contract.functions.set_position_balance(
        wallet.address, int(no_token_id, 16), no_balance_wei
    )
    
    # Set initial USDC balance
    usdc_contract.functions.set_usdc_balance(
        wallet.address, initial_usdc_wei
    )
    
    async def test_merge():
        # Get USDC balance before merge
        usdc_before = await position_merger.get_usdc_balance()
        
        # Execute merge (mock will automatically update USDC balance)
        try:
            receipt = await position_merger.merge_positions(
                condition_id=condition_id,
                yes_token_id=yes_token_id,
                no_token_id=no_token_id,
                amount=merge_amount
            )
            
            # Get USDC balance after merge
            usdc_after = await position_merger.get_usdc_balance()
            
            # Calculate redemption
            usdc_redeemed = usdc_after - usdc_before
            
            # INVARIANT: Redemption should equal merge amount (1:1 ratio)
            # Allow small tolerance for rounding (0.01 USDC)
            tolerance = Decimal('0.01')
            
            assert abs(usdc_redeemed - merge_amount) <= tolerance, \
                f"Redemption invariant violated: " \
                f"merged {merge_amount} positions, " \
                f"redeemed {usdc_redeemed} USDC " \
                f"(difference: {abs(usdc_redeemed - merge_amount)})"
            
            # Verify receipt indicates success
            assert receipt['status'] == 1, \
                "Merge transaction should succeed"
            
            # Verify USDC balance increased by exactly merge_amount
            expected_usdc_after = usdc_before + merge_amount
            assert abs(usdc_after - expected_usdc_after) <= tolerance, \
                f"USDC balance should increase by {merge_amount}: " \
                f"before={usdc_before}, after={usdc_after}, " \
                f"expected={expected_usdc_after}"
            
        except InsufficientBalanceError:
            # This should not happen since we set sufficient balances
            pytest.fail("Unexpected InsufficientBalanceError")
        except MergeRedemptionError as e:
            # This indicates the invariant was violated
            pytest.fail(f"Merge redemption invariant violated: {e}")
    
    # Run test
    asyncio.run(test_merge())


@given(
    merge_amount=st.decimals(
        min_value='0.1',
        max_value='50.0',
        places=2
    ),
    initial_usdc=st.decimals(
        min_value='0.0',
        max_value='5000.0',
        places=2
    )
)
@settings(max_examples=100, deadline=None)
def test_merge_redemption_exact_one_dollar_per_pair(merge_amount, initial_usdc):
    """
    **Validates: Requirement 1.6**
    
    Feature: polymarket-arbitrage-bot, Property 4: Position Merge Redemption Invariant
    
    Verify that merging positions always redeems exactly $1.00 USDC per position pair,
    regardless of the original purchase prices or market conditions.
    
    This is the core invariant: 1 YES + 1 NO = $1.00 USDC
    """
    # Setup
    web3 = MockWeb3()
    wallet = MockAccount()
    
    position_merger = PositionMerger(
        web3=web3,
        ctf_contract_address="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wallet=wallet
    )
    
    # Setup test data
    condition_id = "0x" + "c" * 64
    yes_token_id = "0x" + "1" * 64
    no_token_id = "0x" + "2" * 64
    
    # Set sufficient balances
    balance_multiplier = Decimal('2.0')
    yes_balance_wei = int(merge_amount * balance_multiplier * Decimal(10 ** 6))
    no_balance_wei = int(merge_amount * balance_multiplier * Decimal(10 ** 6))
    initial_usdc_wei = int(initial_usdc * Decimal(10 ** 6))
    
    # Configure mock balances
    ctf_contract = position_merger.ctf_contract
    usdc_contract = position_merger.usdc_contract
    
    # Link USDC contract to eth mock for balance simulation
    web3.eth._usdc_contract = usdc_contract
    
    ctf_contract.functions.set_position_balance(
        wallet.address, int(yes_token_id, 16), yes_balance_wei
    )
    ctf_contract.functions.set_position_balance(
        wallet.address, int(no_token_id, 16), no_balance_wei
    )
    usdc_contract.functions.set_usdc_balance(
        wallet.address, initial_usdc_wei
    )
    
    async def test_exact_redemption():
        # Get initial USDC
        usdc_before = await position_merger.get_usdc_balance()
        
        # Execute merge (mock will automatically update USDC balance)
        receipt = await position_merger.merge_positions(
            condition_id=condition_id,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            amount=merge_amount
        )
        
        # Get final USDC
        usdc_after = await position_merger.get_usdc_balance()
        
        # Calculate actual redemption
        actual_redemption = usdc_after - usdc_before
        
        # CORE INVARIANT: redemption = merge_amount (1 position pair = $1.00)
        redemption_ratio = actual_redemption / merge_amount if merge_amount > 0 else Decimal('0')
        
        # Ratio should be exactly 1.0 (within tolerance)
        tolerance = Decimal('0.01') / merge_amount if merge_amount > 0 else Decimal('0.01')
        
        assert abs(redemption_ratio - Decimal('1.0')) <= tolerance, \
            f"Redemption ratio should be 1.0: " \
            f"merged {merge_amount} pairs, " \
            f"redeemed {actual_redemption} USDC, " \
            f"ratio={redemption_ratio}"
        
        # Verify exact dollar amount
        assert abs(actual_redemption - merge_amount) <= Decimal('0.01'), \
            f"Should redeem exactly ${merge_amount}: got ${actual_redemption}"
    
    # Run test
    asyncio.run(test_exact_redemption())


@given(
    num_merges=st.integers(min_value=1, max_value=10),
    merge_amounts=st.lists(
        st.decimals(min_value='0.1', max_value='10.0', places=2),
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=50, deadline=None)
def test_merge_redemption_cumulative_invariant(num_merges, merge_amounts):
    """
    **Validates: Requirement 1.6**
    
    Feature: polymarket-arbitrage-bot, Property 4: Position Merge Redemption Invariant
    
    Verify that the redemption invariant holds cumulatively across multiple merges.
    Total USDC redeemed should equal sum of all merge amounts.
    """
    assume(len(merge_amounts) >= num_merges)
    
    # Setup
    web3 = MockWeb3()
    wallet = MockAccount()
    
    position_merger = PositionMerger(
        web3=web3,
        ctf_contract_address="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wallet=wallet
    )
    
    # Setup test data
    condition_id = "0x" + "c" * 64
    yes_token_id = "0x" + "1" * 64
    no_token_id = "0x" + "2" * 64
    
    # Calculate total merge amount
    total_merge_amount = sum(merge_amounts[:num_merges])
    
    # Set large initial balances
    initial_balance = total_merge_amount * Decimal('2.0')
    initial_balance_wei = int(initial_balance * Decimal(10 ** 6))
    initial_usdc_wei = int(Decimal('1000.0') * Decimal(10 ** 6))
    
    # Configure mock balances
    ctf_contract = position_merger.ctf_contract
    usdc_contract = position_merger.usdc_contract
    
    # Link USDC contract to eth mock for balance simulation
    web3.eth._usdc_contract = usdc_contract
    
    ctf_contract.functions.set_position_balance(
        wallet.address, int(yes_token_id, 16), initial_balance_wei
    )
    ctf_contract.functions.set_position_balance(
        wallet.address, int(no_token_id, 16), initial_balance_wei
    )
    usdc_contract.functions.set_usdc_balance(
        wallet.address, initial_usdc_wei
    )
    
    async def test_cumulative():
        # Get initial USDC
        usdc_start = await position_merger.get_usdc_balance()
        
        total_redeemed = Decimal('0')
        
        # Perform multiple merges
        for i in range(num_merges):
            merge_amount = merge_amounts[i]
            
            # Execute merge (mock will automatically update USDC balance)
            receipt = await position_merger.merge_positions(
                condition_id=condition_id,
                yes_token_id=yes_token_id,
                no_token_id=no_token_id,
                amount=merge_amount
            )
            
            total_redeemed += merge_amount
        
        # Get final USDC
        usdc_end = await position_merger.get_usdc_balance()
        
        # Calculate total redemption
        actual_total_redemption = usdc_end - usdc_start
        
        # CUMULATIVE INVARIANT: total redemption = sum of merge amounts
        tolerance = Decimal('0.01') * num_merges  # Allow tolerance per merge
        
        assert abs(actual_total_redemption - total_redeemed) <= tolerance, \
            f"Cumulative redemption invariant violated: " \
            f"merged {total_redeemed} total positions, " \
            f"redeemed {actual_total_redemption} USDC " \
            f"(difference: {abs(actual_total_redemption - total_redeemed)})"
        
        # Verify total matches sum of individual merges
        assert abs(total_redeemed - total_merge_amount) <= Decimal('0.01'), \
            f"Total merge amount mismatch: " \
            f"expected {total_merge_amount}, got {total_redeemed}"
    
    # Run test
    asyncio.run(test_cumulative())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
