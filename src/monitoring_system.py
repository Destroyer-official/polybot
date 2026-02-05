"""
Monitoring System for Polymarket Arbitrage Bot.

Provides:
- Prometheus metrics (counters, gauges, histograms)
- SNS alerting
- Trade and error recording
- Metrics exposure on port 9090

Validates Requirements: 13.1, 13.2, 13.5
"""

import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass, field

from prometheus_client import (
    Counter, Gauge, Histogram, start_http_server, CollectorRegistry
)

try:
    import boto3
    SNS_AVAILABLE = True
except ImportError:
    SNS_AVAILABLE = False

from src.models import TradeResult, HealthStatus
from src.logging_config import get_logger, log_with_context


@dataclass
class MetricsSummary:
    """Summary of current metrics"""
    # Trade metrics
    total_trades: int
    successful_trades: int
    failed_trades: int
    win_rate: Decimal
    
    # Financial metrics
    total_profit: Decimal
    total_gas_cost: Decimal
    net_profit: Decimal
    avg_profit_per_trade: Decimal
    
    # Performance metrics
    avg_latency_ms: float
    
    # System metrics
    balance_eoa: Decimal
    balance_proxy: Decimal
    balance_total: Decimal
    gas_price_gwei: int
    pending_tx_count: int
    
    # Safety metrics
    circuit_breaker_open: bool
    consecutive_failures: int


class MonitoringSystem:
    """
    Monitoring system with Prometheus metrics and SNS alerting.
    
    Validates Requirements:
    - 13.1: Expose Prometheus metrics on port 9090
    - 13.2: Update metrics in real-time after each trade
    - 13.5: Send SNS alerts for critical conditions
    """
    
    def __init__(
        self,
        prometheus_port: int = 9090,
        sns_topic_arn: Optional[str] = None,
        enable_prometheus: bool = True,
    ):
        """
        Initialize monitoring system.
        
        Args:
            prometheus_port: Port to expose Prometheus metrics (default 9090)
            sns_topic_arn: AWS SNS topic ARN for alerts
            enable_prometheus: Whether to enable Prometheus metrics server
        """
        self.logger = get_logger(__name__)
        self.prometheus_port = prometheus_port
        self.sns_topic_arn = sns_topic_arn
        self.enable_prometheus = enable_prometheus
        
        # Initialize Prometheus registry
        self.registry = CollectorRegistry()
        
        # Initialize metrics
        self._init_counter_metrics()
        self._init_gauge_metrics()
        self._init_histogram_metrics()
        
        # Initialize SNS client
        self.sns_client = None
        if sns_topic_arn and SNS_AVAILABLE:
            try:
                self.sns_client = boto3.client('sns')
                self.logger.info(f"SNS alerting enabled: {sns_topic_arn}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize SNS client: {e}")
        
        # Start Prometheus HTTP server
        if enable_prometheus:
            try:
                start_http_server(prometheus_port, registry=self.registry)
                self.logger.info(f"Prometheus metrics exposed on port {prometheus_port}")
            except Exception as e:
                self.logger.error(f"Failed to start Prometheus server: {e}")
    
    def _init_counter_metrics(self):
        """Initialize Prometheus counter metrics."""
        # Trade counters
        self.trades_total = Counter(
            'trades_total',
            'Total trades executed',
            ['strategy', 'status'],
            registry=self.registry
        )
        
        self.trades_successful = Counter(
            'trades_successful',
            'Successful trades',
            ['strategy'],
            registry=self.registry
        )
        
        self.trades_failed = Counter(
            'trades_failed',
            'Failed trades',
            ['strategy', 'reason'],
            registry=self.registry
        )
        
        # Opportunity counters
        self.opportunities_found = Counter(
            'opportunities_found',
            'Opportunities detected',
            ['strategy'],
            registry=self.registry
        )
        
        self.opportunities_skipped = Counter(
            'opportunities_skipped',
            'Opportunities skipped',
            ['reason'],
            registry=self.registry
        )
        
        # Safety counters
        self.ai_safety_checks = Counter(
            'ai_safety_checks',
            'AI safety checks',
            ['result'],
            registry=self.registry
        )
        
        # Error counters
        self.network_errors = Counter(
            'network_errors',
            'Network errors',
            ['type'],
            registry=self.registry
        )
        
        self.api_calls = Counter(
            'api_calls',
            'API calls',
            ['endpoint', 'status'],
            registry=self.registry
        )
    
    def _init_gauge_metrics(self):
        """Initialize Prometheus gauge metrics."""
        # Balance gauges
        self.balance_eoa_usd = Gauge(
            'balance_eoa_usd',
            'EOA wallet USDC balance',
            registry=self.registry
        )
        
        self.balance_proxy_usd = Gauge(
            'balance_proxy_usd',
            'Proxy wallet USDC balance',
            registry=self.registry
        )
        
        self.balance_total_usd = Gauge(
            'balance_total_usd',
            'Total USDC balance',
            registry=self.registry
        )
        
        # Financial gauges
        self.profit_usd = Gauge(
            'profit_usd',
            'Total profit in USD',
            registry=self.registry
        )
        
        self.profit_net_usd = Gauge(
            'profit_net_usd',
            'Net profit after gas in USD',
            registry=self.registry
        )
        
        self.win_rate = Gauge(
            'win_rate',
            'Win rate percentage',
            registry=self.registry
        )
        
        # Network gauges
        self.gas_price_gwei = Gauge(
            'gas_price_gwei',
            'Current gas price',
            registry=self.registry
        )
        
        self.pending_tx_count = Gauge(
            'pending_tx_count',
            'Pending transactions',
            registry=self.registry
        )
        
        # System gauges
        self.markets_scanned = Gauge(
            'markets_scanned',
            'Markets in last scan',
            registry=self.registry
        )
        
        self.circuit_breaker_status = Gauge(
            'circuit_breaker_status',
            'Circuit breaker status (0=closed, 1=open)',
            registry=self.registry
        )
        
        self.consecutive_failures = Gauge(
            'consecutive_failures',
            'Consecutive failed trades',
            registry=self.registry
        )
    
    def _init_histogram_metrics(self):
        """Initialize Prometheus histogram metrics."""
        # Latency histograms
        self.latency_ms = Histogram(
            'latency_ms',
            'Execution latency in milliseconds',
            ['operation'],
            registry=self.registry
        )
        
        # Financial histograms
        self.profit_per_trade = Histogram(
            'profit_per_trade',
            'Profit per trade in USD',
            registry=self.registry
        )
        
        self.gas_cost_per_trade = Histogram(
            'gas_cost_per_trade',
            'Gas cost per trade in USD',
            registry=self.registry
        )
        
        # Performance histograms
        self.scan_duration_ms = Histogram(
            'scan_duration_ms',
            'Market scan duration in milliseconds',
            registry=self.registry
        )
        
        self.ai_response_time_ms = Histogram(
            'ai_response_time_ms',
            'AI safety check response time',
            registry=self.registry
        )
    
    def record_trade(self, trade: TradeResult) -> None:
        """
        Record a trade execution and update all metrics.
        
        Validates Requirement 13.2: Update metrics in real-time after each trade
        
        Args:
            trade: TradeResult object containing trade details
        """
        strategy = trade.opportunity.strategy
        status = "success" if trade.was_successful() else "failed"
        
        # Update counter metrics
        self.trades_total.labels(strategy=strategy, status=status).inc()
        
        if trade.was_successful():
            self.trades_successful.labels(strategy=strategy).inc()
            
            # Update financial histograms
            self.profit_per_trade.observe(float(trade.actual_profit))
            self.gas_cost_per_trade.observe(float(trade.gas_cost))
        else:
            reason = trade.error_message or "unknown"
            self.trades_failed.labels(strategy=strategy, reason=reason).inc()
        
        # Log trade
        log_with_context(
            self.logger,
            "info",
            f"Trade {status}: {trade.trade_id}",
            context={
                "trade_id": trade.trade_id,
                "market_id": trade.opportunity.market_id,
                "strategy": strategy,
                "status": status,
                "profit": float(trade.actual_profit),
                "gas_cost": float(trade.gas_cost),
                "net_profit": float(trade.net_profit),
            }
        )
    
    def record_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        recovery_action: Optional[str] = None,
    ) -> None:
        """
        Record an error with full context logging.
        
        Validates Requirement 21.12: Include full context in error logs
        
        Args:
            error: Exception that occurred
            context: Optional context dictionary
            recovery_action: Optional description of recovery action taken
        """
        error_context = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            **(context or {}),
        }
        
        if recovery_action:
            error_context["recovery_action"] = recovery_action
        
        # Log error with full context and stack trace
        log_with_context(
            self.logger,
            "error",
            f"Error occurred: {str(error)}",
            error_context,
            exc_info=True
        )
    
    async def send_alert(
        self,
        severity: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send SNS alert for critical conditions.
        
        Validates Requirement 13.5: Send SNS alerts for critical conditions
        
        Args:
            severity: Alert severity (INFO, WARNING, ERROR, CRITICAL)
            message: Alert message
            context: Optional context dictionary
            
        Returns:
            bool: True if alert sent successfully, False otherwise
        """
        if not self.sns_client or not self.sns_topic_arn:
            self.logger.warning(f"SNS not configured, alert not sent: {message}")
            return False
        
        try:
            # Format alert message
            alert_subject = f"[{severity}] Polymarket Arbitrage Bot Alert"
            alert_body = f"{message}\n\n"
            
            if context:
                alert_body += "Context:\n"
                for key, value in context.items():
                    alert_body += f"  {key}: {value}\n"
            
            alert_body += f"\nTimestamp: {datetime.utcnow().isoformat()}Z"
            
            # Send SNS message
            response = self.sns_client.publish(
                TopicArn=self.sns_topic_arn,
                Subject=alert_subject,
                Message=alert_body,
            )
            
            self.logger.info(f"Alert sent: {message} (MessageId: {response['MessageId']})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send SNS alert: {e}")
            return False
    
    def update_balance_metrics(
        self,
        eoa_balance: Decimal,
        proxy_balance: Decimal,
    ) -> None:
        """
        Update balance gauge metrics.
        
        Args:
            eoa_balance: EOA wallet balance in USDC
            proxy_balance: Proxy wallet balance in USDC
        """
        self.balance_eoa_usd.set(float(eoa_balance))
        self.balance_proxy_usd.set(float(proxy_balance))
        self.balance_total_usd.set(float(eoa_balance + proxy_balance))
    
    def update_financial_metrics(
        self,
        total_profit: Decimal,
        total_gas_cost: Decimal,
        win_rate: Decimal,
    ) -> None:
        """
        Update financial gauge metrics.
        
        Args:
            total_profit: Total profit in USDC
            total_gas_cost: Total gas cost in USDC
            win_rate: Win rate as percentage (0-100)
        """
        self.profit_usd.set(float(total_profit))
        self.profit_net_usd.set(float(total_profit - total_gas_cost))
        self.win_rate.set(float(win_rate))
    
    def update_network_metrics(
        self,
        gas_price: int,
        pending_tx: int,
    ) -> None:
        """
        Update network gauge metrics.
        
        Args:
            gas_price: Current gas price in gwei
            pending_tx: Number of pending transactions
        """
        self.gas_price_gwei.set(gas_price)
        self.pending_tx_count.set(pending_tx)
    
    def update_system_metrics(
        self,
        markets_scanned: int,
        circuit_breaker_open: bool,
        consecutive_failures: int,
    ) -> None:
        """
        Update system gauge metrics.
        
        Args:
            markets_scanned: Number of markets scanned
            circuit_breaker_open: Whether circuit breaker is open
            consecutive_failures: Number of consecutive failures
        """
        self.markets_scanned.set(markets_scanned)
        self.circuit_breaker_status.set(1 if circuit_breaker_open else 0)
        self.consecutive_failures.set(consecutive_failures)
    
    def record_opportunity(
        self,
        strategy: str,
        skipped: bool = False,
        skip_reason: Optional[str] = None,
    ) -> None:
        """
        Record an opportunity detection.
        
        Args:
            strategy: Strategy type (internal, cross_platform, etc.)
            skipped: Whether opportunity was skipped
            skip_reason: Reason for skipping (if skipped)
        """
        if skipped and skip_reason:
            self.opportunities_skipped.labels(reason=skip_reason).inc()
        else:
            self.opportunities_found.labels(strategy=strategy).inc()
    
    def record_ai_safety_check(self, approved: bool) -> None:
        """
        Record an AI safety check result.
        
        Args:
            approved: Whether trade was approved
        """
        result = "approved" if approved else "rejected"
        self.ai_safety_checks.labels(result=result).inc()
    
    def record_network_error(self, error_type: str) -> None:
        """
        Record a network error.
        
        Args:
            error_type: Type of network error
        """
        self.network_errors.labels(type=error_type).inc()
    
    def record_api_call(self, endpoint: str, status: str) -> None:
        """
        Record an API call.
        
        Args:
            endpoint: API endpoint called
            status: Call status (success, failure, timeout)
        """
        self.api_calls.labels(endpoint=endpoint, status=status).inc()
    
    def record_latency(self, operation: str, latency_ms: float) -> None:
        """
        Record operation latency.
        
        Args:
            operation: Operation name
            latency_ms: Latency in milliseconds
        """
        self.latency_ms.labels(operation=operation).observe(latency_ms)
    
    def record_scan_duration(self, duration_ms: float) -> None:
        """
        Record market scan duration.
        
        Args:
            duration_ms: Scan duration in milliseconds
        """
        self.scan_duration_ms.observe(duration_ms)
    
    def record_ai_response_time(self, response_time_ms: float) -> None:
        """
        Record AI safety check response time.
        
        Args:
            response_time_ms: Response time in milliseconds
        """
        self.ai_response_time_ms.observe(response_time_ms)
    
    def get_metrics_summary(self) -> MetricsSummary:
        """
        Get current metrics summary.
        
        Returns:
            MetricsSummary object with current metrics
        """
        # Note: This is a simplified implementation
        # In production, you'd query the actual metric values from Prometheus
        return MetricsSummary(
            total_trades=0,
            successful_trades=0,
            failed_trades=0,
            win_rate=Decimal('0'),
            total_profit=Decimal('0'),
            total_gas_cost=Decimal('0'),
            net_profit=Decimal('0'),
            avg_profit_per_trade=Decimal('0'),
            avg_latency_ms=0.0,
            balance_eoa=Decimal('0'),
            balance_proxy=Decimal('0'),
            balance_total=Decimal('0'),
            gas_price_gwei=0,
            pending_tx_count=0,
            circuit_breaker_open=False,
            consecutive_failures=0,
        )
