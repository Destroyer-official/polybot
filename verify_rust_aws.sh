#!/bin/bash
set -e

echo "=== POLYBOT RUST BUILD CHECK ==="

# 1. Check Rust Installation
if ! command -v cargo &> /dev/null; then
    echo "❌ Rust is NOT installed."
    echo "Run: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
else
    echo "✅ Rust found: $(cargo --version)"
fi

# 2. Check rust_core
CORE_DIR="$HOME/polybot/rust_core"
if [ ! -d "$CORE_DIR" ]; then
    echo "❌ rust_core directory not found at $CORE_DIR"
    exit 1
fi

echo "Building rust_core..."
cd "$CORE_DIR"
cargo clean
cargo check
if cargo build --release; then
    echo "✅ rust_core built successfully!"
else
    echo "❌ rust_core build failed!"
    exit 1
fi

# 3. Check Python Integration
echo "Checking Python integration..."
cd "$HOME/polybot"
source venv/bin/activate
pip install maturin
maturin develop --release

if python3 -c "import rust_core; print('✅ Rust module imported successfully!')"; then
    echo "🎉 RUST ENVIRONMENT VERIFIED"
else
    echo "❌ Failed to import rust_core in Python"
    exit 1
fi
