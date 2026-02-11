#!/usr/bin/env python3
"""
Live Terminal GUI Monitor - Reads real-time logs from journalctl
Shows all bot activity in a beautiful dashboard
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
from rich.align import Align

console = Console()


class LiveBotMonitor:
    """Real-time bot monitoring from journalctl logs"""
    
    def __init__(self, service_name="polybot", max_logs=50, test_mode=False):
        self.service_name = service_name
        self.max_logs = max_logs
        self.test_mode = test_mode
        
        # Data storage
        self.logs = deque(maxlen=max_logs)
        self.ensemble_votes = {}
        self.last_consensus = 0
        self.last_action = "waiting"
        self.gas_price = 0
        self.markets_scanned = 0
        self.opportunities_found = 0
        self.trades_placed = 0
        self.last_error = None
        self.binance_prices = {}
        self.active_positions = 0
        
        # Setup layout
        self.layout = Layout()
        self._setup_layout()
        
        # Start log reader thread
        self.running = True
        self.log_thread = Thread(target=self._read_logs, daemon=True)
        self.log_thread.start()
    
    def _setup_layout(self):
        """Setup dashboard layout"""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        self.layout["main"].split_row(
            Layout(name="left", ratio=3),
            Layout(name="right", ratio=2)
        )
        
        self.layout["left"].split_column(
            Layout(name="metrics", size=10),
            Layout(name="ensemble", size=12),
            Layout(name="logs", ratio=1)
        )
        
        self.layout["right"].split_column(
            Layout(name="markets", size=15),
            Layout(name="status", ratio=1)
        )
    
    def _read_logs(self):
        """Read logs from journalctl in real-time"""
        try:
            if self.test_mode:
                # Test mode: read from log file
                self._read_from_file()
            else:
                # Production mode: read from journalctl
                self._read_from_journalctl()
        except Exception as e:
            self.last_error = f"Log reader error: {e}"
    
    def _read_from_file(self):
        """Read logs from file for testing"""
        import os
        log_files = ['logs/bot_debug.log', 'logs/bot_8hr_full_aws.log']
        
        for log_file in log_files:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    # Read last 100 lines
                    lines = f.readlines()[-100:]
                    for line in lines:
                        self._parse_log_line(line)
                        self.logs.append(line.strip())
                break
        
        # Keep updating in test mode
        while self.running:
            time.sleep(2)
    
    def _read_from_journalctl(self):
        """Read logs from journalctl"""
        # Start journalctl process
        process = subprocess.Popen(
            ['journalctl', '-u', self.service_name, '-f', '-n', '0'],
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
        """Parse log line and extract metrics"""
        try:
            # Gas price
            if "Gas price:" in line:
                match = re.search(r'Gas price: (\d+) gwei', line)
                if match:
                    self.gas_price = int(match.group(1))
            
            # Markets scanned
            if "Parsed" in line and "tradeable markets" in line:
                match = re.search(r'Parsed (\d+) tradeable markets', line)
                if match:
                    self.markets_scanned = int(match.group(1))
            
            # Ensemble votes - parse from reasoning line
            if "Ensemble vote:" in line:
                # Extract all model votes from one line: "LLM: buy_both (100%), RL: skip (50%), ..."
                llm_match = re.search(r'LLM: (\w+) \((\d+)%\)', line)
                if llm_match:
                    self.ensemble_votes['LLM'] = {'action': llm_match.group(1), 'confidence': int(llm_match.group(2))}
                
                rl_match = re.search(r'RL: (\w+) \((\d+)%\)', line)
                if rl_match:
                    self.ensemble_votes['RL'] = {'action': rl_match.group(1), 'confidence': int(rl_match.group(2))}
                
                hist_match = re.search(r'Historical: (\w+) \((\d+)%\)', line)
                if hist_match:
                    self.ensemble_votes['Historical'] = {'action': hist_match.group(1), 'confidence': int(hist_match.group(2))}
                
                tech_match = re.search(r'Technical: (\w+) \((\d+)%\)', line)
                if tech_match:
                    self.ensemble_votes['Technical'] = {'action': tech_match.group(1), 'confidence': int(tech_match.group(2))}
            
            # Consensus - look for "Consensus: X%"
            if "Consensus:" in line:
                match = re.search(r'Consensus: ([\d.]+)%', line)
                if match:
                    self.last_consensus = float(match.group(1))
            
            # Action - look for ENSEMBLE APPROVED/REJECTED
            if "ENSEMBLE APPROVED:" in line:
                match = re.search(r'ENSEMBLE APPROVED: (\w+)', line)
                if match:
                    self.last_action = f"✅ {match.group(1)}"
                    self.opportunities_found += 1
            elif "ENSEMBLE REJECTED:" in line:
                match = re.search(r'ENSEMBLE REJECTED: (\w+)', line)
                if match:
                    self.last_action = f"❌ {match.group(1)}"
            elif "SUM-TO-ONE CHECK:" in line:
                self.last_action = "🔍 sum-to-one"
            elif "LATENCY CHECK:" in line:
                self.last_action = "🔍 latency"
            elif "DIRECTIONAL CHECK:" in line:
                self.last_action = "🔍 directional"
            
            # Binance prices
            if "Binance=$" in line:
                match = re.search(r'(\w+) \| Binance=\$([\d.]+)', line)
                if match:
                    asset = match.group(1)
                    price = float(match.group(2))
                    self.binance_prices[asset] = price
            
            # Active positions
            if "Active positions:" in line:
                match = re.search(r'Active positions: (\d+)', line)
                if match:
                    self.active_positions = int(match.group(1))
            
            # Trades placed
            if "ORDER PLACED SUCCESSFULLY" in line:
                self.trades_placed += 1
            
            # Errors
            if "ERROR" in line or "CRITICAL" in line:
                self.last_error = line[-100:]  # Last 100 chars
        
        except Exception:
            pass  # Ignore parsing errors
    
    def _make_header(self) -> Panel:
        """Create header"""
        now = datetime.now().strftime("%H:%M:%S")
        
        header_text = Text()
        header_text.append("🤖 ", style="bold cyan")
        header_text.append("LIVE BOT MONITOR", style="bold white")
        header_text.append(f"  |  {now}", style="dim")
        
        return Panel(header_text, style="bold cyan", box=box.DOUBLE)
    
    def _make_metrics(self) -> Panel:
        """Create metrics panel"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan", width=18)
        table.add_column("Value", style="white", width=20)
        
        # Gas price with color
        gas_color = "green" if self.gas_price < 800 else "red"
        
        table.add_row("⛽ Gas Price", f"[{gas_color}]{self.gas_price} gwei[/{gas_color}]")
        table.add_row("📊 Markets Scanned", f"{self.markets_scanned}")
        table.add_row("🔍 Opportunities", f"[yellow]{self.opportunities_found}[/yellow]")
        table.add_row("📈 Active Positions", f"[cyan]{self.active_positions}[/cyan]")
        table.add_row("💰 Trades Placed", f"[green]{self.trades_placed}[/green]")
        
        return Panel(
            table,
            title="[bold cyan]📊 Live Metrics[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED
        )
    
    def _make_ensemble(self) -> Panel:
        """Create ensemble voting panel"""
        table = Table(box=box.SIMPLE)
        table.add_column("Model", style="cyan", width=12)
        table.add_column("Action", width=12)
        table.add_column("Confidence", width=12)
        
        for model in ['LLM', 'RL', 'Historical', 'Technical']:
            if model in self.ensemble_votes:
                vote = self.ensemble_votes[model]
                action = vote['action']
                conf = vote['confidence']
                
                # Color based on action
                if action in ['buy_yes', 'buy_no', 'buy_both']:
                    action_color = "green"
                elif action == 'skip':
                    action_color = "red"
                else:
                    action_color = "yellow"
                
                conf_color = "green" if conf >= 50 else "yellow" if conf >= 25 else "red"
                
                table.add_row(
                    f"{'🧠' if model == 'LLM' else '🤖' if model == 'RL' else '📊' if model == 'Historical' else '📈'} {model}",
                    f"[{action_color}]{action}[/{action_color}]",
                    f"[{conf_color}]{conf}%[/{conf_color}]"
                )
            else:
                table.add_row(f"{model}", "[dim]waiting...[/dim]", "[dim]-[/dim]")
        
        # Consensus row
        consensus_color = "green" if self.last_consensus >= 15 else "red"
        table.add_row("", "", "")
        table.add_row(
            "[bold]Consensus[/bold]",
            f"[bold]{self.last_action}[/bold]",
            f"[bold {consensus_color}]{self.last_consensus:.1f}%[/bold {consensus_color}]"
        )
        
        return Panel(
            table,
            title="[bold magenta]🎯 Ensemble Decision[/bold magenta]",
            border_style="magenta",
            box=box.ROUNDED
        )
    
    def _make_markets(self) -> Panel:
        """Create markets panel"""
        if not self.binance_prices:
            return Panel(
                "[dim]Waiting for market data...[/dim]",
                title="[bold yellow]📈 Binance Prices[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED
            )
        
        table = Table(box=box.SIMPLE)
        table.add_column("Asset", style="cyan", width=8)
        table.add_column("Price", width=15)
        
        for asset, price in self.binance_prices.items():
            table.add_row(asset, f"${price:,.2f}")
        
        return Panel(
            table,
            title="[bold yellow]📈 Binance Prices[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED
        )
    
    def _make_status(self) -> Panel:
        """Create status panel"""
        if self.last_error:
            status_text = Text()
            status_text.append("⚠️ Last Error:\n", style="bold red")
            status_text.append(self.last_error[-200:], style="red")
            return Panel(
                status_text,
                title="[bold red]Status[/bold red]",
                border_style="red",
                box=box.ROUNDED
            )
        else:
            return Panel(
                "[green]✅ Bot running smoothly[/green]",
                title="[bold green]Status[/bold green]",
                border_style="green",
                box=box.ROUNDED
            )
    
    def _make_logs(self) -> Panel:
        """Create logs panel"""
        log_text = Text()
        
        for log in list(self.logs)[-15:]:  # Show last 15 lines
            # Color code logs
            if "ERROR" in log or "CRITICAL" in log:
                log_text.append(log[-100:] + "\n", style="red")
            elif "WARNING" in log:
                log_text.append(log[-100:] + "\n", style="yellow")
            elif "ENSEMBLE APPROVED" in log:
                log_text.append(log[-100:] + "\n", style="green bold")
            elif "ORDER PLACED" in log:
                log_text.append(log[-100:] + "\n", style="green")
            else:
                log_text.append(log[-100:] + "\n", style="dim")
        
        return Panel(
            log_text,
            title="[bold white]📜 Recent Logs[/bold white]",
            border_style="white",
            box=box.ROUNDED
        )
    
    def _make_footer(self) -> Panel:
        """Create footer"""
        footer_text = Text()
        footer_text.append("Press ", style="dim")
        footer_text.append("Ctrl+C", style="bold red")
        footer_text.append(" to exit  |  ", style="dim")
        footer_text.append(f"Monitoring: {self.service_name}", style="dim cyan")
        
        return Panel(footer_text, style="dim", box=box.ROUNDED)
    
    def render(self) -> Layout:
        """Render the dashboard"""
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
    import sys
    
    # Check for test mode
    test_mode = '--test' in sys.argv or '-t' in sys.argv
    
    console.clear()
    if test_mode:
        console.print("[bold cyan]Starting Bot Monitor in TEST MODE...[/bold cyan]")
        console.print("[dim]Reading from log files...[/dim]")
    else:
        console.print("[bold cyan]Starting Live Bot Monitor...[/bold cyan]")
        console.print("[dim]Reading logs from journalctl...[/dim]")
    time.sleep(1)
    
    monitor = LiveBotMonitor(test_mode=test_mode)
    
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
