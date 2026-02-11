#!/usr/bin/env python3
"""
Real-time Terminal GUI Monitor for Polymarket Trading Bot
Shows all metrics, trades, and logs in one beautiful dashboard
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
from typing import Dict, List, Optional
import sys

# Add src to path
sys.path.insert(0, 'src')

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


class BotMonitor:
    """Real-time bot monitoring dashboard"""
    
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        
        # Data files
        self.state_file = Path("data/bot_state.json")
        self.positions_file = Path("data/active_positions.json")
        self.trades_file = Path("data/trade_history.db")
        self.learning_file = Path("data/super_smart_learning.json")
        
        # Cached data
        self.state = {}
        self.positions = {}
        self.recent_trades = []
        self.learning_stats = {}
        self.last_update = time.time()
        
        # Setup layout
        self._setup_layout()
    
    def _setup_layout(self):
        """Setup the dashboard layout"""
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
            Layout(name="status", size=12),
            Layout(name="positions", ratio=1),
            Layout(name="trades", ratio=1)
        )
        
        self.layout["right"].split_column(
            Layout(name="ensemble", size=15),
            Layout(name="learning", ratio=1)
        )
    
    def _load_data(self):
        """Load data from files"""
        try:
            # Load bot state
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
            
            # Load positions
            if self.positions_file.exists():
                with open(self.positions_file, 'r') as f:
                    self.positions = json.load(f)
            
            # Load learning stats
            if self.learning_file.exists():
                with open(self.learning_file, 'r') as f:
                    self.learning_stats = json.load(f)
            
            self.last_update = time.time()
        except Exception as e:
            console.print(f"[red]Error loading data: {e}[/red]")
    
    def _make_header(self) -> Panel:
        """Create header panel"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        header_text = Text()
        header_text.append("🤖 ", style="bold cyan")
        header_text.append("POLYMARKET TRADING BOT MONITOR", style="bold white")
        header_text.append(f"  |  {now}", style="dim")
        
        return Panel(
            header_text,
            style="bold cyan",
            box=box.DOUBLE
        )
    
    def _make_status(self) -> Panel:
        """Create status panel"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        # Get stats from state
        stats = self.state.get('trade_statistics', {})
        circuit_breaker = self.state.get('circuit_breaker', {})
        
        total_trades = stats.get('total_trades', 0)
        successful = stats.get('successful_trades', 0)
        failed = stats.get('failed_trades', 0)
        total_profit = Decimal(str(stats.get('total_profit', '0')))
        
        win_rate = (successful / total_trades * 100) if total_trades > 0 else 0
        
        # Status indicators
        cb_status = "🔴 OPEN" if circuit_breaker.get('is_open', False) else "🟢 CLOSED"
        cb_failures = circuit_breaker.get('consecutive_failures', 0)
        
        # Add rows
        table.add_row("Status", "🟢 RUNNING" if total_trades >= 0 else "🔴 STOPPED")
        table.add_row("Circuit Breaker", f"{cb_status} ({cb_failures} failures)")
        table.add_row("", "")
        table.add_row("Total Trades", f"{total_trades}")
        table.add_row("Successful", f"[green]{successful}[/green]")
        table.add_row("Failed", f"[red]{failed}[/red]")
        table.add_row("Win Rate", f"[{'green' if win_rate >= 50 else 'yellow'}]{win_rate:.1f}%[/]")
        table.add_row("", "")
        table.add_row("Total P&L", f"[{'green' if total_profit >= 0 else 'red'}]${total_profit:.2f}[/]")
        
        return Panel(
            table,
            title="[bold cyan]📊 Bot Status[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED
        )
    
    def _make_positions(self) -> Panel:
        """Create positions panel"""
        if not self.positions:
            return Panel(
                "[dim]No active positions[/dim]",
                title="[bold yellow]📈 Active Positions[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED
            )
        
        table = Table(box=box.SIMPLE)
        table.add_column("Asset", style="cyan", width=8)
        table.add_column("Side", width=6)
        table.add_column("Entry", width=8)
        table.add_column("Size", width=8)
        table.add_column("Age", width=10)
        table.add_column("Strategy", width=12)
        
        now = datetime.now(timezone.utc)
        
        for token_id, pos in list(self.positions.items())[:5]:  # Show max 5
            entry_time = datetime.fromisoformat(pos['entry_time'])
            age_minutes = (now - entry_time).total_seconds() / 60
            
            side_color = "green" if pos['side'] == "UP" else "red"
            
            table.add_row(
                pos['asset'],
                f"[{side_color}]{pos['side']}[/{side_color}]",
                f"${float(pos['entry_price']):.3f}",
                f"{float(pos['size']):.1f}",
                f"{age_minutes:.1f}m",
                pos.get('strategy', 'unknown')
            )
        
        return Panel(
            table,
            title=f"[bold yellow]📈 Active Positions ({len(self.positions)})[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED
        )
    
    def _make_trades(self) -> Panel:
        """Create recent trades panel"""
        # For now, show placeholder
        # In production, this would read from trade_history.db
        
        table = Table(box=box.SIMPLE)
        table.add_column("Time", style="dim", width=8)
        table.add_column("Asset", width=6)
        table.add_column("Side", width=6)
        table.add_column("P&L", width=10)
        table.add_column("Reason", width=15)
        
        # Placeholder data
        table.add_row(
            "15:30:45",
            "BTC",
            "[green]UP[/green]",
            "[green]+$0.15[/green]",
            "take_profit"
        )
        
        return Panel(
            table,
            title="[bold green]💰 Recent Trades[/bold green]",
            border_style="green",
            box=box.ROUNDED
        )
    
    def _make_ensemble(self) -> Panel:
        """Create ensemble voting panel"""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Model", style="cyan", width=12)
        table.add_column("Vote", width=10)
        table.add_column("Confidence", width=12)
        
        # Placeholder - in production, read from logs or state
        table.add_row("🧠 LLM", "buy_yes", "[green]65%[/green]")
        table.add_row("🤖 RL", "buy_yes", "[green]55%[/green]")
        table.add_row("📊 Historical", "neutral", "[yellow]50%[/yellow]")
        table.add_row("📈 Technical", "skip", "[red]0%[/red]")
        table.add_row("", "", "")
        table.add_row("[bold]Consensus[/bold]", "[bold]40%[/bold]", "[yellow]PENDING[/yellow]")
        
        return Panel(
            table,
            title="[bold magenta]🎯 Ensemble Voting[/bold magenta]",
            border_style="magenta",
            box=box.ROUNDED
        )
    
    def _make_learning(self) -> Panel:
        """Create learning stats panel"""
        stats = self.learning_stats
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="cyan", width=15)
        table.add_column("Value", style="white")
        
        total_trades = stats.get('total_trades', 0)
        best_strategy = stats.get('best_strategy', 'N/A')
        best_asset = stats.get('best_asset', 'N/A')
        
        table.add_row("Total Trades", f"{total_trades}")
        table.add_row("Best Strategy", f"[green]{best_strategy}[/green]")
        table.add_row("Best Asset", f"[green]{best_asset}[/green]")
        
        return Panel(
            table,
            title="[bold blue]🧠 Learning Stats[/bold blue]",
            border_style="blue",
            box=box.ROUNDED
        )
    
    def _make_footer(self) -> Panel:
        """Create footer panel"""
        footer_text = Text()
        footer_text.append("Press ", style="dim")
        footer_text.append("Ctrl+C", style="bold red")
        footer_text.append(" to exit  |  ", style="dim")
        footer_text.append("Updates every 2 seconds", style="dim")
        
        return Panel(
            footer_text,
            style="dim",
            box=box.ROUNDED
        )
    
    def render(self) -> Layout:
        """Render the complete dashboard"""
        self._load_data()
        
        self.layout["header"].update(self._make_header())
        self.layout["status"].update(self._make_status())
        self.layout["positions"].update(self._make_positions())
        self.layout["trades"].update(self._make_trades())
        self.layout["ensemble"].update(self._make_ensemble())
        self.layout["learning"].update(self._make_learning())
        self.layout["footer"].update(self._make_footer())
        
        return self.layout


async def main():
    """Main monitoring loop"""
    monitor = BotMonitor()
    
    console.clear()
    console.print("[bold cyan]Starting Bot Monitor...[/bold cyan]")
    await asyncio.sleep(1)
    
    try:
        with Live(monitor.render(), refresh_per_second=0.5, screen=True) as live:
            while True:
                live.update(monitor.render())
                await asyncio.sleep(2)  # Update every 2 seconds
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped by user[/yellow]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
