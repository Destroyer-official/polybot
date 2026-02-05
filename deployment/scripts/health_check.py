#!/usr/bin/env python3
"""
Health check script for Polymarket Arbitrage Bot (Python version)
Can be run standalone or imported as a module
"""

import os
import sys
import json
import subprocess
import requests
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class HealthCheckResult:
    """Result of a single health check"""
    name: str
    status: str  # "pass", "fail", "warn", "info"
    message: str
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class HealthChecker:
    """Health checker for Polymarket Arbitrage Bot"""
    
    def __init__(self, bot_dir: str = "/home/botuser/polymarket-bot"):
        self.bot_dir = Path(bot_dir)
        self.service_name = "polymarket-bot"
        self.prometheus_port = 9090
        self.min_balance = 10.0
        
        self.results: List[HealthCheckResult] = []
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = 0
    
    def add_result(self, name: str, status: str, message: str):
        """Add a check result"""
        result = HealthCheckResult(name=name, status=status, message=message)
        self.results.append(result)
        
        if status == "pass":
            self.checks_passed += 1
        elif status == "fail":
            self.checks_failed += 1
        elif status == "warn":
            self.warnings += 1
    
    def run_command(self, cmd: List[str], timeout: int = 5) -> Tuple[bool, str]:
        """Run a shell command and return success status and output"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def check_system_components(self):
        """Check if all system components are present"""
        # Bot directory
        if self.bot_dir.exists():
            self.add_result("Bot Directory", "pass", f"Found at {self.bot_dir}")
        else:
            self.add_result("Bot Directory", "fail", f"Not found at {self.bot_dir}")
        
        # Virtual environment
        venv_dir = self.bot_dir / "venv"
        if venv_dir.exists():
            self.add_result("Python Virtual Environment", "pass", "Found")
        else:
            self.add_result("Python Virtual Environment", "fail", "Not found")
        
        # Rust module
        rust_lib = self.bot_dir / "rust_core" / "target" / "release" / "librust_core.so"
        if rust_lib.exists():
            self.add_result("Rust Core Module", "pass", "Built successfully")
        else:
            self.add_result("Rust Core Module", "warn", "Not found or not built")
    
    def check_service_status(self):
        """Check systemd service status"""
        # Service file exists
        service_file = Path(f"/etc/systemd/system/{self.service_name}.service")
        if service_file.exists():
            self.add_result("Systemd Service File", "pass", "Found")
        else:
            self.add_result("Systemd Service File", "fail", "Not found")
            return
        
        # Service enabled
        success, _ = self.run_command(["systemctl", "is-enabled", self.service_name])
        if success:
            self.add_result("Service Auto-Start", "pass", "Enabled")
        else:
            self.add_result("Service Auto-Start", "warn", "Not enabled")
        
        # Service active
        success, _ = self.run_command(["systemctl", "is-active", self.service_name])
        if success:
            self.add_result("Service Running", "pass", "Active")
            
            # Get uptime
            success, uptime = self.run_command([
                "systemctl", "show", self.service_name,
                "--property=ActiveEnterTimestamp", "--value"
            ])
            if success:
                self.add_result("Service Uptime", "info", f"Started at {uptime}")
        else:
            self.add_result("Service Running", "fail", "Not active")
    
    def check_configuration(self):
        """Check configuration files"""
        env_file = self.bot_dir / ".env"
        
        if env_file.exists():
            self.add_result("Environment File", "pass", f"Found at {env_file}")
            
            # Read env file
            try:
                with open(env_file, 'r') as f:
                    env_content = f.read()
                
                # Check for private key config
                if "PRIVATE_KEY" in env_content or "USE_AWS_SECRETS=true" in env_content:
                    self.add_result("Private Key Config", "pass", "Configured")
                else:
                    self.add_result("Private Key Config", "fail", "Not configured")
                
                # Check DRY_RUN mode
                if "DRY_RUN=true" in env_content:
                    self.add_result("DRY_RUN Mode", "warn", "Enabled (no real trades)")
                else:
                    self.add_result("DRY_RUN Mode", "info", "Disabled (live trading)")
            except Exception as e:
                self.add_result("Environment File", "fail", f"Error reading: {e}")
        else:
            self.add_result("Environment File", "fail", "Not found")
    
    def check_aws_integration(self):
        """Check AWS integration"""
        # AWS CLI
        success, _ = self.run_command(["which", "aws"])
        if not success:
            self.add_result("AWS CLI", "warn", "Not installed")
            return
        
        self.add_result("AWS CLI", "pass", "Installed")
        
        # AWS credentials
        success, _ = self.run_command(["aws", "sts", "get-caller-identity"])
        if success:
            self.add_result("AWS Credentials", "pass", "Valid")
        else:
            self.add_result("AWS Credentials", "fail", "Not configured or invalid")
    
    def check_api_connectivity(self):
        """Check API connectivity"""
        # Polymarket API
        try:
            response = requests.get("https://clob.polymarket.com/markets", timeout=5)
            if response.status_code == 200:
                self.add_result("Polymarket API", "pass", "Reachable")
            else:
                self.add_result("Polymarket API", "fail", f"HTTP {response.status_code}")
        except Exception as e:
            self.add_result("Polymarket API", "fail", f"Not reachable: {e}")
        
        # Polygon RPC
        rpc_url = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
        try:
            response = requests.post(
                rpc_url,
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=5
            )
            if response.status_code == 200:
                self.add_result("Polygon RPC", "pass", f"Reachable at {rpc_url}")
            else:
                self.add_result("Polygon RPC", "fail", f"HTTP {response.status_code}")
        except Exception as e:
            self.add_result("Polygon RPC", "fail", f"Not reachable: {e}")
        
        # Internet connectivity
        success, _ = self.run_command(["ping", "-c", "1", "8.8.8.8"])
        if success:
            self.add_result("Internet Connectivity", "pass", "Online")
        else:
            self.add_result("Internet Connectivity", "fail", "Offline")
    
    def check_wallet_balance(self):
        """Check wallet balance from Prometheus metrics"""
        try:
            response = requests.get(f"http://localhost:{self.prometheus_port}/metrics", timeout=5)
            if response.status_code != 200:
                self.add_result("Wallet Balance", "warn", "Prometheus metrics not available")
                return
            
            metrics = response.text
            
            # Parse balance metrics
            for line in metrics.split('\n'):
                if line.startswith('balance_total_usd '):
                    balance = float(line.split()[1])
                    if balance >= self.min_balance:
                        self.add_result("Total Balance", "pass", f"${balance:.2f} USDC")
                    else:
                        self.add_result("Total Balance", "warn", 
                                      f"${balance:.2f} USDC (below minimum ${self.min_balance})")
                
                elif line.startswith('balance_eoa_usd '):
                    balance = float(line.split()[1])
                    self.add_result("EOA Wallet Balance", "info", f"${balance:.2f} USDC")
                
                elif line.startswith('balance_proxy_usd '):
                    balance = float(line.split()[1])
                    self.add_result("Proxy Wallet Balance", "info", f"${balance:.2f} USDC")
        
        except Exception as e:
            self.add_result("Wallet Balance", "warn", f"Unable to retrieve: {e}")
    
    def check_monitoring_metrics(self):
        """Check monitoring and metrics"""
        try:
            response = requests.get(f"http://localhost:{self.prometheus_port}/metrics", timeout=5)
            if response.status_code != 200:
                self.add_result("Prometheus Metrics", "fail", "Not available")
                return
            
            self.add_result("Prometheus Metrics", "pass", 
                          f"Available at http://localhost:{self.prometheus_port}/metrics")
            
            metrics = response.text
            
            # Parse key metrics
            for line in metrics.split('\n'):
                if line.startswith('trades_total '):
                    trades = int(float(line.split()[1]))
                    self.add_result("Total Trades", "info", f"{trades} trades executed")
                
                elif line.startswith('win_rate '):
                    win_rate = float(line.split()[1])
                    if win_rate >= 95:
                        self.add_result("Win Rate", "pass", f"{win_rate:.1f}%")
                    else:
                        self.add_result("Win Rate", "warn", f"{win_rate:.1f}% (below 95%)")
                
                elif line.startswith('profit_usd '):
                    profit = float(line.split()[1])
                    self.add_result("Total Profit", "info", f"${profit:.2f} USD")
        
        except Exception as e:
            self.add_result("Prometheus Metrics", "fail", f"Not available: {e}")
    
    def check_system_resources(self):
        """Check system resources"""
        # CPU usage
        success, output = self.run_command(["top", "-bn1"])
        if success:
            for line in output.split('\n'):
                if 'Cpu(s)' in line:
                    cpu_usage = float(line.split()[1].replace('%us,', ''))
                    if cpu_usage < 80:
                        self.add_result("CPU Usage", "pass", f"{cpu_usage:.1f}%")
                    else:
                        self.add_result("CPU Usage", "warn", f"{cpu_usage:.1f}% (high)")
                    break
        
        # Memory usage
        success, output = self.run_command(["free"])
        if success:
            lines = output.split('\n')
            if len(lines) > 1:
                mem_line = lines[1].split()
                total = int(mem_line[1])
                used = int(mem_line[2])
                mem_usage = (used / total) * 100
                if mem_usage < 80:
                    self.add_result("Memory Usage", "pass", f"{mem_usage:.1f}%")
                else:
                    self.add_result("Memory Usage", "warn", f"{mem_usage:.1f}% (high)")
        
        # Disk usage
        success, output = self.run_command(["df", "-h", "/"])
        if success:
            lines = output.split('\n')
            if len(lines) > 1:
                disk_line = lines[1].split()
                disk_usage = int(disk_line[4].replace('%', ''))
                if disk_usage < 80:
                    self.add_result("Disk Usage", "pass", f"{disk_usage}%")
                else:
                    self.add_result("Disk Usage", "warn", f"{disk_usage}% (high)")
    
    def check_recent_logs(self):
        """Check recent logs for errors"""
        success, output = self.run_command([
            "journalctl", "-u", self.service_name,
            "--since", "1 hour ago"
        ], timeout=10)
        
        if success:
            error_count = output.lower().count('error')
            
            if error_count == 0:
                self.add_result("Recent Errors", "pass", "No errors in last hour")
            elif error_count < 10:
                self.add_result("Recent Errors", "warn", f"{error_count} errors in last hour")
            else:
                self.add_result("Recent Errors", "fail", f"{error_count} errors in last hour")
        else:
            self.add_result("Recent Logs", "warn", "Unable to check logs")
    
    def check_deployment_status(self):
        """Check overall deployment status"""
        # Check if service is running and configured
        service_running = any(r.name == "Service Running" and r.status == "pass" 
                            for r in self.results)
        env_configured = any(r.name == "Environment File" and r.status == "pass" 
                           for r in self.results)
        
        if service_running and env_configured:
            self.add_result("Deployment Status", "pass", "Bot is deployed and running")
        else:
            self.add_result("Deployment Status", "fail", "Bot is not fully deployed")
    
    def run_all_checks(self) -> Dict:
        """Run all health checks"""
        print("Running health checks...")
        
        self.check_system_components()
        self.check_service_status()
        self.check_configuration()
        self.check_aws_integration()
        self.check_api_connectivity()
        self.check_wallet_balance()
        self.check_monitoring_metrics()
        self.check_system_resources()
        self.check_recent_logs()
        self.check_deployment_status()
        
        return self.get_summary()
    
    def get_summary(self) -> Dict:
        """Get health check summary"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "warnings": self.warnings,
            "overall_status": self.get_overall_status(),
            "results": [asdict(r) for r in self.results]
        }
    
    def get_overall_status(self) -> str:
        """Get overall health status"""
        if self.checks_failed == 0:
            if self.warnings == 0:
                return "HEALTHY"
            else:
                return "HEALTHY_WITH_WARNINGS"
        else:
            return "UNHEALTHY"
    
    def print_report(self):
        """Print formatted health check report"""
        print("\n" + "="*60)
        print("Polymarket Arbitrage Bot - Health Check Report")
        print("="*60)
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        print()
        
        for result in self.results:
            status_symbol = {
                "pass": "✓",
                "fail": "✗",
                "warn": "⚠",
                "info": "ℹ"
            }.get(result.status, "?")
            
            print(f"{status_symbol} {result.name}: {result.status.upper()} - {result.message}")
        
        print()
        print("="*60)
        print("Summary")
        print("="*60)
        print(f"Checks Passed:  {self.checks_passed}")
        print(f"Checks Failed:  {self.checks_failed}")
        print(f"Warnings:       {self.warnings}")
        print(f"Overall Status: {self.get_overall_status()}")
        print()


def main():
    """Main entry point"""
    bot_dir = os.getenv("BOT_DIR", "/home/botuser/polymarket-bot")
    
    checker = HealthChecker(bot_dir=bot_dir)
    summary = checker.run_all_checks()
    
    # Print report
    checker.print_report()
    
    # Output JSON if requested
    if "--json" in sys.argv:
        print(json.dumps(summary, indent=2))
    
    # Exit with appropriate code
    if summary["overall_status"] == "UNHEALTHY":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
