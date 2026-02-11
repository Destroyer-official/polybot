#!/usr/bin/env python3
"""
Premium Real-Time Terminal Monitor for Polymarket Trading Bot
100% Real Data - No Placeholders - Advanced Structure
"""
import subprocess
import re
import time
from datetime import datetime
from collections import deque
from threading import Thread
import sys

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich import box
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

console = Console()


class PremiumBotMonitor:
    """Premium real-time bot monitoring with 100% real data"""
    
    def __init__(self, service_name="polybot", max_logs=100, test_mode=False):
        self.service_name = service_name
        self.max_logs = max_logs
        self.test_mode = test_mode
        
        # Real-time data storage
        self.logs = deque(maxlen=max_logs)
        self.ensemble_votes = {}
        self.last_consensus = 0.0
        self.last_confidence = 0.0
        self.last_action = "initializing"
        self.last_action_time = None
        
        # Metrics
        self.gas_price = 0
        self.balance = 0.0
        self.markets_scanned = 0
        self.opportunities_found = 0
        self.opportunities_rejected = 0
        self.trades_placed = 0
        self.active_positions = 0
        
        # Market data
        self.binance_prices = {}
        self.current_markets = {}  # asset -> {up_price, down_price, sum}
        
        # Errors and warnings
        self.last_error = None
        self.last_warning = None
        self.slippage_rejections = 0
        
        # Performance tracking
        self.scan_count = 0
        self.last_scan_time = None
        self.uptime_start = datetime.now()
        
        # Setup layout
        self.layout = Layout()
        self._setup_layout()
        
        # Start log reader thread
        self.running = True
        self.log_thread = Thread(target=self._read_logs, daemon=True)
        self.log_thread.start()
    
    def _setup_layout(self):
        """Setup premium dashboard layout"""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        self.layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        self.layout["left"].split_column(
            Layout(name="metrics", size=14),
            Layout(name="ensemble", size=14),
            Layout(name="logs", ratio=1)
        )
        
        self.layout["right"].split_column(
            Layout(name="markets", size=18),
            Layout(name="status", ratio=1)
        )
    
    def _read_logs(self):
        """Read logs from journalctl or file"""
        try:
            if self.test_mode:
                self._read_from_file()
            else:
                self._read_from_journalctl()
        except Exception as e:
            self.last_error = f"Log reader error: {e}"
    
    def _read_from_file(self):
        """Read from log file for testing"""
        import os
        log_files = ['logs/bot_debug.log', 'logs/bot_8hr_full_aws.log']
        
        for log_file in log_files:
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[-200:]
                    for line in lines:
                        self._parse_log_line(line)
                        self.logs.append(line.strip())
                break
        
        while self.running:
            time.sleep(2)
    
    def _read_from_journalctl(self):
        """Read from journalctl in real-time"""
        process = subprocess.Popen(
            ['journalctl', '-u', self.service_name, '-f', '-n', '50'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        for line in process.stdout:
            if not self.running:
                break
            self._parse_log_line(line)
            self.logs.append(line.strip())
    
    def _parse_log_line(self, line: str):
        """Parse log line and extract all real data"""
        try:
            # Gas price
            if "Gas price:" in line:
                match = re.search(r'Gas price: (\d+) gwei', line)
                if match:
                    self.gas_price = int(match.group(1))
            
            # Balance
            if "Balance=$" in line or "balance=$" in line:
                match = re.search(r'[Bb]alance=\$?([\d.]+)', line)
                if match:
                    self.balance = float(match.group(1))
            
            # Markets scanned
            if "Parsed" in line and "tradeable markets" in line:
                match = re.search(r'Parsed (\d+) tradeable markets', line)
                if match:
                    self.markets_scanned = int(match.group(1))
                    self.scan_count += 1
                    self.last_scan_time = datetime.now()
            
            # Current market prices - parse from CURRENT or SUM-TO-ONE logs
            if "CURRENT" in line and "market:" in line:
                # Extract: "🎯 CURRENT BTC market: Up=$0.56, Down=$0.44"
                asset_match = re.search(r'CURRENT (\w+) market:', line, re.IGNORECASE)
                up_match = re.search(r'Up=\$([\d.]+)', line, re.IGNORECASE)
                down_match = re.search(r'Down=\$([\d.]+)', line, re.IGNORECASE)
                
                if asset_match and up_match and down_match:
                    asset = asset_match.group(1).upper()
                    up_price = float(up_match.group(1))
                    down_price = float(down_match.group(1))
                    self.current_markets[asset] = {
                        'up': up_price,
                        'down': down_price,
                        'sum': up_price + down_price
                    }
            
            elif "SUM-TO-ONE CHECK:" in line:
                # Extract: "💰 SUM-TO-ONE CHECK: BTC | UP=$0.560 + DOWN=$0.440 = $1.000"
                asset_match = re.search(r'SUM-TO-ONE CHECK: (\w+)', line)
                up_match = re.search(r'UP=\$([\d.]+)', line)
                down_match = re.search(r'DOWN=\$([\d.]+)', line)
                
                if asset_match and up_match and down_match:
                    asset = asset_match.group(1).upper()
                    up_price = float(up_match.group(1))
                    down_price = float(down_match.group(1))
                    self.current_markets[asset] = {
                        'up': up_price,
                        'down': down_price,
                        'sum': up_price + down_price
                    }
            
            # Ensemble votes from individual model log lines
            if re.search(r'^\s+(LLM|RL|Historical|Technical):', line):
                # Extract: "   LLM: buy_both (50%) - Market Rebalancing: YES + NO < $1.00"
                model_match = re.search(r'(LLM|RL|Historical|Technical):\s*(\w+)\s*\((\d+)%\)', line)
                if model_match:
                    model = model_match.group(1)
                    action = model_match.group(2)
                    confidence = int(model_match.group(3))
                    self.ensemble_votes[model] = {
                        'action': action,
                        'confidence': confidence
                    }
            
            # Consensus and confidence
            if "Consensus:" in line:
                match = re.search(r'Consensus: ([\d.]+)%', line)
                if match:
                    self.last_consensus = float(match.group(1))
            
            if "Confidence:" in line and "Ensemble" not in line:
                match = re.search(r'Confidence: ([\d.]+)%', line)
                if match:
                    self.last_confidence = float(match.group(1))
            
            # Ensemble decisions
            if "ENSEMBLE APPROVED:" in line:
                match = re.search(r'ENSEMBLE APPROVED: (\w+)', line)
                if match:
                    self.last_action = f"✅ APPROVED: {match.group(1)}"
                    self.last_action_time = datetime.now()
                    self.opportunities_found += 1
            
            elif "ENSEMBLE REJECTED:" in line:
                match = re.search(r'ENSEMBLE REJECTED: (\w+)', line)
                if match:
                    self.last_action = f"❌ REJECTED: {match.group(1)}"
                    self.last_action_time = datetime.now()
                    self.opportunities_rejected += 1
            
            # Strategy checks
            elif "SUM-TO-ONE CHECK:" in line:
                self.last_action = "🔍 Checking sum-to-one arbitrage"
            elif "LATENCY CHECK:" in line:
                self.last_action = "🔍 Checking latency arbitrage"
            elif "DIRECTIONAL CHECK:" in line:
                self.last_action = "🔍 Checking directional trade"
            
            # Binance prices - handle both formats with/without commas
            if "Binance=$" in line or "Binance =" in line:
                # Extract: "ETH | Binance=$1935.07" or "ETH | Binance=$1,935.07"
                match = re.search(r'(\w+)\s*\|\s*Binance\s*=?\s*\$([\d,]+\.?\d*)', line)
                if match:
                    asset = match.group(1).upper()
                    price_str = match.group(2).replace(',', '')
                    try:
                        self.binance_prices[asset] = float(price_str)
                    except ValueError:
                        pass
            
            # Active positions
            if "Active positions:" in line:
                match = re.search(r'Active positions: (\d+)', line)
                if match:
                    self.active_positions = int(match.group(1))
            
            # Trades placed
            if "ORDER PLACED SUCCESSFULLY" in line or "📈 PLACING ORDER" in line:
                self.trades_placed += 1
            
            # Slippage rejections
            if "Excessive slippage" in line:
                self.slippage_rejections += 1
                match = re.search(r'slippage \(estimated: ([\d.]+)%', line)
                if match:
                    self.last_warning = f"High slippage: {match.group(1)}%"
            
            # Errors
            if " ERROR " in line or " CRITICAL " in line:
                # Extract just the message part
                parts = line.split(" - ")
                if len(parts) >= 3:
                    self.last_error = parts[-1][:150]
            
            # Warnings
            if " WARNING " in line and "slippage" not in line.lower():
                parts = line.split(" - ")
                if len(parts) >= 3:
                    self.last_warning = parts[-1][:150]
        
        except Exception:
            pass  # Ignore parsing errors
    
    def _make_header(self) -> Panel:
        """Create premium header"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uptime = datetime.now() - self.uptime_start
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
        
        header_text = Text()
        header_text.append("🤖 ", style="bold cyan")
        header_text.append("POLYMARKET BOT ", style="bold white")
        header_text.append("PREMIUM MONITOR", style="bold cyan")
        header_text.append(f"  |  {now}", style="dim")
        header_text.append(f"  |  Uptime: {uptime_str}", style="dim green")
        
        return Panel(header_text, style="bold cyan", box=box.DOUBLE)
    
    def _make_metrics(self) -> Panel:
        """Create metrics panel with real data"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan", width=22)
        table.add_column("Value", style="white", width=25)
        
        # Gas price with color
        gas_color = "green" if self.gas_price < 800 else "yellow" if self.gas_price < 1200 else "red"
        
        # Balance with color
        balance_color = "green" if self.balance >= 10 else "yellow" if self.balance >= 5 else "red"
        
        # Scan rate
        scan_rate = "N/A"
        if self.last_scan_time:
            elapsed = (datetime.now() - self.uptime_start).total_seconds()
            if elapsed > 0:
                scan_rate = f"{self.scan_count / elapsed:.1f}/s"
        
        table.add_row("⛽ Gas Price", f"[{gas_color}]{self.gas_price} gwei[/{gas_color}]")
        table.add_row("💰 Balance", f"[{balance_color}]${self.balance:.2f}[/{balance_color}]")
        table.add_row("", "")
        table.add_row("📊 Markets Scanned", f"{self.markets_scanned}")
        table.add_row("📈 Scan Rate", f"[dim]{scan_rate}[/dim]")
        table.add_row("", "")
        table.add_row("✅ Opportunities Found", f"[green]{self.opportunities_found}[/green]")
        table.add_row("❌ Opportunities Rejected", f"[red]{self.opportunities_rejected}[/red]")
        table.add_row("🚫 Slippage Rejections", f"[yellow]{self.slippage_rejections}[/yellow]")
        table.add_row("", "")
        table.add_row("📍 Active Positions", f"[cyan]{self.active_positions}[/cyan]")
        table.add_row("💸 Trades Placed", f"[green bold]{self.trades_placed}[/green bold]")
        
        return Panel(
            table,
            title="[bold cyan]📊 Live Metrics (Real-Time)[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED
        )
    
    def _make_ensemble(self) -> Panel:
        """Create ensemble panel with real votes"""
        table = Table(box=box.SIMPLE)
        table.add_column("Model", style="cyan", width=14)
        table.add_column("Action", width=12)
        table.add_column("Confidence", width=12)
        
        models_found = 0
        for model in ['LLM', 'RL', 'Historical', 'Technical']:
            if model in self.ensemble_votes:
                vote = self.ensemble_votes[model]
                action = vote['action']
                conf = vote['confidence']
                models_found += 1
                
                # Color based on action
                if action in ['buy_yes', 'buy_no', 'buy_both']:
                    action_color = "green"
                elif action == 'skip':
                    action_color = "red"
                else:
                    action_color = "yellow"
                
                conf_color = "green" if conf >= 50 else "yellow" if conf >= 25 else "red"
                
                icon = {'LLM': '🧠', 'RL': '🤖', 'Historical': '📊', 'Technical': '📈'}[model]
                
                table.add_row(
                    f"{icon} {model}",
                    f"[{action_color}]{action}[/{action_color}]",
                    f"[{conf_color}]{conf}%[/{conf_color}]"
                )
            else:
                table.add_row(f"{model}", "[dim]waiting...[/dim]", "[dim]-[/dim]")
        
        # Consensus row
        table.add_row("", "", "")
        consensus_color = "green" if self.last_consensus >= 10 else "red"
        confidence_color = "green" if self.last_confidence >= 50 else "yellow" if self.last_confidence >= 25 else "red"
        
        table.add_row(
            "[bold]Consensus[/bold]",
            f"[bold {consensus_color}]{self.last_consensus:.1f}%[/bold {consensus_color}]",
            f"[{confidence_color}]{self.last_confidence:.1f}%[/{confidence_color}]"
        )
        
        # Last action
        table.add_row("", "", "")
        action_time = ""
        if self.last_action_time:
            elapsed = (datetime.now() - self.last_action_time).total_seconds()
            action_time = f" ({elapsed:.0f}s ago)"
        
        table.add_row(
            "[bold]Last Action[/bold]",
            f"[bold]{self.last_action}[/bold]{action_time}",
            ""
        )
        
        title_suffix = f" ({models_found}/4 models)" if models_found < 4 else " (All Models Active)"
        
        return Panel(
            table,
            title=f"[bold magenta]🎯 Ensemble Decision{title_suffix}[/bold magenta]",
            border_style="magenta",
            box=box.ROUNDED
        )
    
    def _make_markets(self) -> Panel:
        """Create markets panel with real data"""
        if not self.binance_prices and not self.current_markets:
            return Panel(
                "[dim]Waiting for market data...[/dim]",
                title="[bold yellow]📈 Market Data[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED
            )
        
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Asset", style="cyan bold", width=6)
        table.add_column("Binance", width=12)
        table.add_column("Poly UP", width=10)
        table.add_column("Poly DOWN", width=10)
        table.add_column("Sum", width=8)
        
        # Combine data from both sources
        all_assets = set(self.binance_prices.keys()) | set(self.current_markets.keys())
        
        for asset in sorted(all_assets):
            binance_price = self.binance_prices.get(asset, 0)
            poly_data = self.current_markets.get(asset, {})
            
            up_price = poly_data.get('up', 0)
            down_price = poly_data.get('down', 0)
            sum_price = poly_data.get('sum', 0)
            
            # Color code sum (green if < 1.00, yellow if = 1.00, red if > 1.00)
            if sum_price > 0:
                if sum_price < 1.00:
                    sum_color = "green"
                elif sum_price == 1.00:
                    sum_color = "yellow"
                else:
                    sum_color = "red"
                sum_str = f"[{sum_color}]${sum_price:.3f}[/{sum_color}]"
            else:
                sum_str = "[dim]-[/dim]"
            
            table.add_row(
                asset,
                f"${binance_price:,.2f}" if binance_price > 0 else "[dim]-[/dim]",
                f"${up_price:.3f}" if up_price > 0 else "[dim]-[/dim]",
                f"${down_price:.3f}" if down_price > 0 else "[dim]-[/dim]",
                sum_str
            )
        
        return Panel(
            table,
            title="[bold yellow]📈 Market Data (Real-Time)[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED
        )
    
    def _make_status(self) -> Panel:
        """Create status panel with real errors/warnings"""
        if self.last_error:
            status_text = Text()
            status_text.append("🔴 ERROR:\n", style="bold red")
            status_text.append(self.last_error, style="red")
            return Panel(
                status_text,
                title="[bold red]Status[/bold red]",
                border_style="red",
                box=box.ROUNDED
            )
        elif self.last_warning:
            status_text = Text()
            status_text.append("⚠️ WARNING:\n", style="bold yellow")
            status_text.append(self.last_warning, style="yellow")
            return Panel(
                status_text,
                title="[bold yellow]Status[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED
            )
        else:
            status_text = Text()
            status_text.append("✅ ", style="green bold")
            status_text.append("Bot running smoothly\n", style="green")
            status_text.append(f"Monitoring: {self.service_name}", style="dim")
            return Panel(
                status_text,
                title="[bold green]Status[/bold green]",
                border_style="green",
                box=box.ROUNDED
            )
    
    def _make_logs(self) -> Panel:
        """Create logs panel with real logs"""
        log_text = Text()
        
        recent_logs = list(self.logs)[-20:]  # Show last 20 lines
        
        if not recent_logs:
            log_text.append("Waiting for logs...", style="dim")
        else:
            for log in recent_logs:
                # Extract just the message part (after timestamp and level)
                parts = log.split(" - ")
                if len(parts) >= 3:
                    message = " - ".join(parts[2:])
                else:
                    message = log
                
                # Truncate long lines
                if len(message) > 120:
                    message = message[:117] + "..."
                
                # Color code
                if "ERROR" in log or "CRITICAL" in log:
                    log_text.append(message + "\n", style="red")
                elif "WARNING" in log:
                    log_text.append(message + "\n", style="yellow")
                elif "ENSEMBLE APPROVED" in log:
                    log_text.append(message + "\n", style="green bold")
                elif "ORDER PLACED" in log:
                    log_text.append(message + "\n", style="green")
                elif "ENSEMBLE REJECTED" in log:
                    log_text.append(message + "\n", style="red dim")
                else:
                    log_text.append(message + "\n", style="dim")
        
        return Panel(
            log_text,
            title="[bold white]📜 Recent Activity (Real-Time)[/bold white]",
            border_style="white",
            box=box.ROUNDED
        )
    
    def _make_footer(self) -> Panel:
        """Create footer"""
        footer_text = Text()
        footer_text.append("Press ", style="dim")
        footer_text.append("Ctrl+C", style="bold red")
        footer_text.append(" to exit", style="dim")
        footer_text.append("  |  ", style="dim")
        footer_text.append("100% Real Data - No Placeholders", style="bold green")
        footer_text.append("  |  ", style="dim")
        footer_text.append(f"Service: {self.service_name}", style="dim cyan")
        
        return Panel(footer_text, style="dim", box=box.ROUNDED)
    
    def render(self) -> Layout:
        """Render the complete dashboard"""
        self.layout["header"].update(self._make_header())
        self.layout["metrics"].update(self._make_metrics())
        self.layout["ensemble"].update(self._make_ensemble())
        self.layout["markets"].update(self._make_markets())
        self.layout["status"].update(self._make_status())
        self.layout["logs"].update(self._make_logs())
        self.layout["footer"].update(self._make_footer())
        
        return self.layout
    
    def stop(self):
        """Stop the monitor"""
        self.running = False


def main():
    """Main function"""
    # Check for test mode
    test_mode = '--test' in sys.argv or '-t' in sys.argv
    
    console.clear()
    if test_mode:
        console.print("[bold cyan]🚀 Starting Premium Bot Monitor (TEST MODE)...[/bold cyan]")
        console.print("[dim]Reading from log files...[/dim]")
    else:
        console.print("[bold cyan]🚀 Starting Premium Bot Monitor (LIVE)...[/bold cyan]")
        console.print("[dim]Connecting to journalctl...[/dim]")
    
    console.print("[green]✓[/green] 100% Real Data - No Placeholders")
    console.print("[green]✓[/green] Advanced Structure - Premium Quality")
    time.sleep(1.5)
    
    monitor = PremiumBotMonitor(test_mode=test_mode)
    
    try:
        with Live(monitor.render(), refresh_per_second=2, screen=True) as live:
            while True:
                live.update(monitor.render())
                time.sleep(0.5)
    except KeyboardInterrupt:
        monitor.stop()
        console.print("\n[yellow]Monitor stopped[/yellow]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
