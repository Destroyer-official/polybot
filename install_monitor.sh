#!/bin/bash
# Quick install script for the monitoring system

echo "🤖 Installing Bot Monitor..."

# Install rich library
echo "📦 Installing rich library..."
pip install rich>=13.0.0

# Make scripts executable
chmod +x monitor.py
chmod +x monitor_live.py

# Check if running on AWS with systemd
if systemctl is-active --quiet polybot; then
    echo "✅ Bot service detected: polybot"
    echo ""
    echo "🎯 To start monitoring, run:"
    echo "   python monitor_live.py"
    echo ""
    echo "💡 Tip: Use tmux for persistent monitoring:"
    echo "   tmux new -s monitor"
    echo "   python monitor_live.py"
    echo "   # Press Ctrl+B then D to detach"
else
    echo "⚠️  Bot service not detected"
    echo ""
    echo "🎯 For local development, run:"
    echo "   python monitor.py"
fi

echo ""
echo "✅ Installation complete!"
