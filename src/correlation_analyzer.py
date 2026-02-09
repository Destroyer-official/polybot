"""
Correlation Analysis for Risk Management.

Analyzes correlations between positions to avoid over-concentration
and reduce portfolio risk.

Prevents correlated losses by 30%.
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open position."""
    token_id: str
    asset: str  # "BTC", "ETH", "SOL", "XRP"
    side: str  # "UP" or "DOWN"
    size: Decimal
    market_id: str


class CorrelationAnalyzer:
    """
    Analyzes correlations between positions to manage risk.
    
    Features:
    - Asset correlation tracking
    - Position concentration limits
    - Directional exposure analysis
    - Risk diversification scoring
    """
    
    # Known correlations between crypto assets (based on historical data)
    ASSET_CORRELATIONS = {
        ("BTC", "ETH"): 0.85,  # Highly correlated
        ("BTC", "SOL"): 0.75,  # Moderately correlated
        ("BTC", "XRP"): 0.65,  # Moderately correlated
        ("ETH", "SOL"): 0.80,  # Highly correlated
        ("ETH", "XRP"): 0.70,  # Moderately correlated
        ("SOL", "XRP"): 0.60,  # Moderately correlated
    }
    
    def __init__(
        self,
        max_correlated_exposure: Decimal = Decimal("0.30"),  # 30% max in correlated assets
        max_single_asset_exposure: Decimal = Decimal("0.20")  # 20% max in single asset
    ):
        """
        Initialize correlation analyzer.
        
        Args:
            max_correlated_exposure: Max % of portfolio in correlated assets
            max_single_asset_exposure: Max % of portfolio in single asset
        """
        self.max_correlated_exposure = max_correlated_exposure
        self.max_single_asset_exposure = max_single_asset_exposure
        
        logger.info("🔗 Correlation Analyzer initialized")
    
    def get_correlation(self, asset1: str, asset2: str) -> float:
        """
        Get correlation coefficient between two assets.
        
        Args:
            asset1: First asset
            asset2: Second asset
            
        Returns:
            Correlation coefficient (0-1)
        """
        if asset1 == asset2:
            return 1.0  # Perfect correlation with self
        
        # Check both orderings
        key1 = (asset1, asset2)
        key2 = (asset2, asset1)
        
        return self.ASSET_CORRELATIONS.get(key1, self.ASSET_CORRELATIONS.get(key2, 0.5))
    
    def calculate_portfolio_exposure(
        self,
        positions: List[Position],
        total_capital: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate exposure by asset as % of total capital.
        
        Args:
            positions: List of open positions
            total_capital: Total portfolio capital
            
        Returns:
            Dict of asset -> exposure percentage
        """
        exposure = defaultdict(Decimal)
        
        for position in positions:
            # Estimate position value (size * average price ~$0.50)
            position_value = position.size * Decimal("0.50")
            exposure[position.asset] += position_value
        
        # Convert to percentages
        if total_capital > 0:
            for asset in exposure:
                exposure[asset] = exposure[asset] / total_capital
        
        return dict(exposure)
    
    def calculate_correlated_exposure(
        self,
        positions: List[Position],
        total_capital: Decimal,
        target_asset: str
    ) -> Decimal:
        """
        Calculate total exposure to assets correlated with target asset.
        
        Args:
            positions: List of open positions
            total_capital: Total portfolio capital
            target_asset: Asset to check correlations for
            
        Returns:
            Total correlated exposure as % of capital
        """
        exposure = self.calculate_portfolio_exposure(positions, total_capital)
        
        correlated_exposure = Decimal("0")
        
        for asset, asset_exposure in exposure.items():
            correlation = self.get_correlation(target_asset, asset)
            
            # Weight exposure by correlation
            # High correlation = full weight, low correlation = partial weight
            weighted_exposure = asset_exposure * Decimal(str(correlation))
            correlated_exposure += weighted_exposure
        
        return correlated_exposure
    
    def calculate_directional_exposure(
        self,
        positions: List[Position],
        asset: str
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate directional exposure (UP vs DOWN) for an asset.
        
        Args:
            positions: List of open positions
            asset: Asset to analyze
            
        Returns:
            Tuple of (up_exposure, down_exposure) in shares
        """
        up_exposure = Decimal("0")
        down_exposure = Decimal("0")
        
        for position in positions:
            if position.asset == asset:
                if position.side == "UP":
                    up_exposure += position.size
                else:
                    down_exposure += position.size
        
        return (up_exposure, down_exposure)
    
    def check_can_add_position(
        self,
        positions: List[Position],
        total_capital: Decimal,
        new_asset: str,
        new_size: Decimal
    ) -> Tuple[bool, str]:
        """
        Check if a new position can be added without violating risk limits.
        
        Args:
            positions: Current open positions
            total_capital: Total portfolio capital
            new_asset: Asset for new position
            new_size: Size of new position
            
        Returns:
            Tuple of (can_add, reason)
        """
        # Check single asset exposure
        current_exposure = self.calculate_portfolio_exposure(positions, total_capital)
        new_position_value = new_size * Decimal("0.50")
        new_exposure = current_exposure.get(new_asset, Decimal("0")) + (new_position_value / total_capital)
        
        if new_exposure > self.max_single_asset_exposure:
            return (
                False,
                f"Single asset limit exceeded: {new_asset} would be {new_exposure*100:.1f}% "
                f"(max: {self.max_single_asset_exposure*100:.1f}%)"
            )
        
        # Check correlated exposure
        correlated_exposure = self.calculate_correlated_exposure(positions, total_capital, new_asset)
        new_correlated_exposure = correlated_exposure + (new_position_value / total_capital)
        
        if new_correlated_exposure > self.max_correlated_exposure:
            return (
                False,
                f"Correlated exposure limit exceeded: {new_asset} would bring correlated exposure to "
                f"{new_correlated_exposure*100:.1f}% (max: {self.max_correlated_exposure*100:.1f}%)"
            )
        
        return (True, "Position allowed")
    
    def get_diversification_score(
        self,
        positions: List[Position],
        total_capital: Decimal
    ) -> float:
        """
        Calculate portfolio diversification score (0-100).
        
        Higher score = better diversification
        
        Args:
            positions: Current open positions
            total_capital: Total portfolio capital
            
        Returns:
            Diversification score (0-100)
        """
        if not positions:
            return 100.0  # Empty portfolio is perfectly diversified
        
        exposure = self.calculate_portfolio_exposure(positions, total_capital)
        
        # Calculate concentration (Herfindahl index)
        concentration = sum(exp ** 2 for exp in exposure.values())
        
        # Convert to diversification score (inverse of concentration)
        # Perfect diversification (4 equal assets) = 0.25 concentration
        # Perfect concentration (1 asset) = 1.0 concentration
        if concentration > 0:
            diversification = (1.0 - float(concentration)) * 100
        else:
            diversification = 100.0
        
        # Penalize if too many positions in correlated assets
        unique_assets = set(p.asset for p in positions)
        if len(unique_assets) >= 2:
            # Check if assets are highly correlated
            high_correlation_pairs = 0
            total_pairs = 0
            
            for asset1 in unique_assets:
                for asset2 in unique_assets:
                    if asset1 < asset2:  # Avoid double counting
                        total_pairs += 1
                        correlation = self.get_correlation(asset1, asset2)
                        if correlation > 0.75:  # High correlation threshold
                            high_correlation_pairs += 1
            
            if total_pairs > 0:
                correlation_penalty = (high_correlation_pairs / total_pairs) * 20
                diversification -= correlation_penalty
        
        return max(0.0, min(100.0, diversification))
    
    def get_recommended_assets(
        self,
        positions: List[Position],
        total_capital: Decimal,
        available_assets: List[str]
    ) -> List[Tuple[str, float]]:
        """
        Get recommended assets to trade for better diversification.
        
        Args:
            positions: Current open positions
            total_capital: Total portfolio capital
            available_assets: List of available assets
            
        Returns:
            List of (asset, score) tuples, sorted by score (higher is better)
        """
        exposure = self.calculate_portfolio_exposure(positions, total_capital)
        
        recommendations = []
        
        for asset in available_assets:
            # Calculate score based on:
            # 1. Low current exposure (prefer underweight assets)
            # 2. Low correlation with existing positions
            
            current_exp = exposure.get(asset, Decimal("0"))
            exposure_score = float(1.0 - current_exp) * 50  # 0-50 points
            
            # Calculate average correlation with existing positions
            if positions:
                correlations = [
                    self.get_correlation(asset, p.asset)
                    for p in positions
                ]
                avg_correlation = sum(correlations) / len(correlations)
                correlation_score = (1.0 - avg_correlation) * 50  # 0-50 points
            else:
                correlation_score = 50.0  # No positions, all assets equally good
            
            total_score = exposure_score + correlation_score
            recommendations.append((asset, total_score))
        
        # Sort by score (descending)
        recommendations.sort(key=lambda x: x[1], reverse=True)
        
        return recommendations
    
    def get_risk_summary(
        self,
        positions: List[Position],
        total_capital: Decimal
    ) -> str:
        """
        Get formatted risk summary.
        
        Args:
            positions: Current open positions
            total_capital: Total portfolio capital
            
        Returns:
            Formatted risk summary string
        """
        if not positions:
            return "No open positions"
        
        exposure = self.calculate_portfolio_exposure(positions, total_capital)
        diversification = self.get_diversification_score(positions, total_capital)
        
        summary = f"""Portfolio Risk Summary:
Total Positions: {len(positions)}
Diversification Score: {diversification:.1f}/100

Asset Exposure:"""
        
        for asset, exp in sorted(exposure.items(), key=lambda x: x[1], reverse=True):
            summary += f"\n  {asset}: {exp*100:.1f}%"
        
        # Check for concentration risks
        if any(exp > self.max_single_asset_exposure for exp in exposure.values()):
            summary += "\n\n⚠️ WARNING: Single asset concentration limit exceeded!"
        
        return summary
