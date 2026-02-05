#!/bin/bash
# Health check script for Polymarket Arbitrage Bot
# Verifies all components are initialized and functioning correctly

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
BOT_USER="botuser"
BOT_HOME="/home/$BOT_USER"
BOT_DIR="$BOT_HOME/polymarket-bot"
SERVICE_NAME="polymarket-bot"
PROMETHEUS_PORT=9090
MIN_BALANCE=10.0

# Status tracking
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Polymarket Arbitrage Bot - Health Check Report          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Timestamp: $(date)"
echo ""

# Function to print check result
check_result() {
    local name="$1"
    local status="$2"
    local message="$3"
    
    if [ "$status" = "pass" ]; then
        echo -e "${GREEN}✓${NC} $name: ${GREEN}PASS${NC} - $message"
        ((CHECKS_PASSED++))
    elif [ "$status" = "fail" ]; then
        echo -e "${RED}✗${NC} $name: ${RED}FAIL${NC} - $message"
        ((CHECKS_FAILED++))
    elif [ "$status" = "warn" ]; then
        echo -e "${YELLOW}⚠${NC} $name: ${YELLOW}WARNING${NC} - $message"
        ((WARNINGS++))
    else
        echo -e "${BLUE}ℹ${NC} $name: ${BLUE}INFO${NC} - $message"
    fi
}

echo -e "${BLUE}[1/10] System Components${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if bot directory exists
if [ -d "$BOT_DIR" ]; then
    check_result "Bot Directory" "pass" "Found at $BOT_DIR"
else
    check_result "Bot Directory" "fail" "Not found at $BOT_DIR"
fi

# Check if virtual environment exists
if [ -d "$BOT_DIR/venv" ]; then
    check_result "Python Virtual Environment" "pass" "Found"
else
    check_result "Python Virtual Environment" "fail" "Not found"
fi

# Check if Rust module is built
if [ -f "$BOT_DIR/rust_core/target/release/librust_core.so" ] || [ -f "$BOT_DIR/rust_core/target/release/rust_core.so" ]; then
    check_result "Rust Core Module" "pass" "Built successfully"
else
    check_result "Rust Core Module" "warn" "Not found or not built"
fi

echo ""
echo -e "${BLUE}[2/10] Service Status${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if systemd service exists
if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    check_result "Systemd Service File" "pass" "Found"
    
    # Check if service is enabled
    if systemctl is-enabled --quiet $SERVICE_NAME 2>/dev/null; then
        check_result "Service Auto-Start" "pass" "Enabled"
    else
        check_result "Service Auto-Start" "warn" "Not enabled"
    fi
    
    # Check if service is active
    if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
        check_result "Service Running" "pass" "Active"
        
        # Get service uptime
        UPTIME=$(systemctl show $SERVICE_NAME --property=ActiveEnterTimestamp --value)
        check_result "Service Uptime" "info" "Started at $UPTIME"
    else
        check_result "Service Running" "fail" "Not active"
        
        # Get service status
        STATUS=$(systemctl status $SERVICE_NAME --no-pager -l 2>&1 | head -n 10)
        echo -e "${RED}Service Status:${NC}"
        echo "$STATUS"
    fi
else
    check_result "Systemd Service File" "fail" "Not found"
fi

echo ""
echo -e "${BLUE}[3/10] Configuration${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if .env file exists
if [ -f "$BOT_DIR/.env" ]; then
    check_result "Environment File" "pass" "Found at $BOT_DIR/.env"
    
    # Check critical environment variables
    if grep -q "PRIVATE_KEY" "$BOT_DIR/.env" || grep -q "USE_AWS_SECRETS=true" "$BOT_DIR/.env"; then
        check_result "Private Key Config" "pass" "Configured"
    else
        check_result "Private Key Config" "fail" "Not configured"
    fi
    
    # Check DRY_RUN mode
    if grep -q "DRY_RUN=true" "$BOT_DIR/.env"; then
        check_result "DRY_RUN Mode" "warn" "Enabled (no real trades)"
    else
        check_result "DRY_RUN Mode" "info" "Disabled (live trading)"
    fi
else
    check_result "Environment File" "fail" "Not found"
fi

echo ""
echo -e "${BLUE}[4/10] AWS Integration${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check AWS CLI
if command -v aws &> /dev/null; then
    check_result "AWS CLI" "pass" "Installed"
    
    # Check AWS credentials
    if aws sts get-caller-identity &> /dev/null; then
        check_result "AWS Credentials" "pass" "Valid"
        
        # Check Secrets Manager access
        if grep -q "USE_AWS_SECRETS=true" "$BOT_DIR/.env" 2>/dev/null; then
            SECRET_NAME=$(grep "SECRET_NAME=" "$BOT_DIR/.env" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
            if [ -n "$SECRET_NAME" ]; then
                if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" &> /dev/null; then
                    check_result "Secrets Manager" "pass" "Secret '$SECRET_NAME' accessible"
                else
                    check_result "Secrets Manager" "fail" "Secret '$SECRET_NAME' not accessible"
                fi
            fi
        fi
        
        # Check CloudWatch Logs access
        LOG_GROUP=$(grep "CLOUDWATCH_LOG_GROUP=" "$BOT_DIR/.env" | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "/polymarket-arbitrage-bot")
        if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" &> /dev/null; then
            check_result "CloudWatch Logs" "pass" "Log group accessible"
        else
            check_result "CloudWatch Logs" "warn" "Log group not found or not accessible"
        fi
    else
        check_result "AWS Credentials" "fail" "Not configured or invalid"
    fi
else
    check_result "AWS CLI" "warn" "Not installed"
fi

echo ""
echo -e "${BLUE}[5/10] API Connectivity${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Polymarket API
if curl -s --max-time 5 "https://clob.polymarket.com/markets" > /dev/null 2>&1; then
    check_result "Polymarket API" "pass" "Reachable"
else
    check_result "Polymarket API" "fail" "Not reachable"
fi

# Check Polygon RPC
RPC_URL=$(grep "POLYGON_RPC_URL=" "$BOT_DIR/.env" | cut -d'=' -f2 | tr -d '"' | tr -d "'" 2>/dev/null || echo "https://polygon-rpc.com")
if curl -s --max-time 5 -X POST -H "Content-Type: application/json" \
    --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
    "$RPC_URL" > /dev/null 2>&1; then
    check_result "Polygon RPC" "pass" "Reachable at $RPC_URL"
else
    check_result "Polygon RPC" "fail" "Not reachable at $RPC_URL"
fi

# Check internet connectivity
if ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    check_result "Internet Connectivity" "pass" "Online"
else
    check_result "Internet Connectivity" "fail" "Offline"
fi

echo ""
echo -e "${BLUE}[6/10] Wallet Balance${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Try to get wallet balance from Prometheus metrics
if curl -s "http://localhost:$PROMETHEUS_PORT/metrics" > /dev/null 2>&1; then
    BALANCE=$(curl -s "http://localhost:$PROMETHEUS_PORT/metrics" | grep "^balance_total_usd" | awk '{print $2}')
    
    if [ -n "$BALANCE" ]; then
        if (( $(echo "$BALANCE >= $MIN_BALANCE" | bc -l) )); then
            check_result "Total Balance" "pass" "\$$BALANCE USDC"
        else
            check_result "Total Balance" "warn" "\$$BALANCE USDC (below minimum \$$MIN_BALANCE)"
        fi
        
        # Get EOA and Proxy balances
        EOA_BALANCE=$(curl -s "http://localhost:$PROMETHEUS_PORT/metrics" | grep "^balance_eoa_usd" | awk '{print $2}')
        PROXY_BALANCE=$(curl -s "http://localhost:$PROMETHEUS_PORT/metrics" | grep "^balance_proxy_usd" | awk '{print $2}')
        
        if [ -n "$EOA_BALANCE" ]; then
            check_result "EOA Wallet Balance" "info" "\$$EOA_BALANCE USDC"
        fi
        
        if [ -n "$PROXY_BALANCE" ]; then
            check_result "Proxy Wallet Balance" "info" "\$$PROXY_BALANCE USDC"
        fi
    else
        check_result "Wallet Balance" "warn" "Unable to retrieve from metrics"
    fi
else
    check_result "Wallet Balance" "warn" "Prometheus metrics not available"
fi

echo ""
echo -e "${BLUE}[7/10] Monitoring & Metrics${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Prometheus metrics endpoint
if curl -s "http://localhost:$PROMETHEUS_PORT/metrics" > /dev/null 2>&1; then
    check_result "Prometheus Metrics" "pass" "Available at http://localhost:$PROMETHEUS_PORT/metrics"
    
    # Get key metrics
    TRADES_TOTAL=$(curl -s "http://localhost:$PROMETHEUS_PORT/metrics" | grep "^trades_total" | awk '{sum+=$2} END {print sum}')
    WIN_RATE=$(curl -s "http://localhost:$PROMETHEUS_PORT/metrics" | grep "^win_rate" | awk '{print $2}')
    PROFIT=$(curl -s "http://localhost:$PROMETHEUS_PORT/metrics" | grep "^profit_usd" | awk '{print $2}')
    
    if [ -n "$TRADES_TOTAL" ]; then
        check_result "Total Trades" "info" "$TRADES_TOTAL trades executed"
    fi
    
    if [ -n "$WIN_RATE" ]; then
        if (( $(echo "$WIN_RATE >= 95" | bc -l) )); then
            check_result "Win Rate" "pass" "$WIN_RATE%"
        else
            check_result "Win Rate" "warn" "$WIN_RATE% (below 95%)"
        fi
    fi
    
    if [ -n "$PROFIT" ]; then
        check_result "Total Profit" "info" "\$$PROFIT USD"
    fi
else
    check_result "Prometheus Metrics" "fail" "Not available"
fi

echo ""
echo -e "${BLUE}[8/10] System Resources${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check CPU usage
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
if (( $(echo "$CPU_USAGE < 80" | bc -l) )); then
    check_result "CPU Usage" "pass" "$CPU_USAGE%"
else
    check_result "CPU Usage" "warn" "$CPU_USAGE% (high)"
fi

# Check memory usage
MEM_USAGE=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
if (( $(echo "$MEM_USAGE < 80" | bc -l) )); then
    check_result "Memory Usage" "pass" "$MEM_USAGE%"
else
    check_result "Memory Usage" "warn" "$MEM_USAGE% (high)"
fi

# Check disk usage
DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
if (( $DISK_USAGE < 80 )); then
    check_result "Disk Usage" "pass" "$DISK_USAGE%"
else
    check_result "Disk Usage" "warn" "$DISK_USAGE% (high)"
fi

echo ""
echo -e "${BLUE}[9/10] Recent Logs${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for recent errors in logs
if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
    ERROR_COUNT=$(journalctl -u $SERVICE_NAME --since "1 hour ago" | grep -i "error" | wc -l)
    
    if [ "$ERROR_COUNT" -eq 0 ]; then
        check_result "Recent Errors" "pass" "No errors in last hour"
    elif [ "$ERROR_COUNT" -lt 10 ]; then
        check_result "Recent Errors" "warn" "$ERROR_COUNT errors in last hour"
    else
        check_result "Recent Errors" "fail" "$ERROR_COUNT errors in last hour"
    fi
    
    # Show last 5 log entries
    echo ""
    echo "Last 5 log entries:"
    journalctl -u $SERVICE_NAME -n 5 --no-pager | tail -n 5
else
    check_result "Recent Logs" "warn" "Service not running"
fi

echo ""
echo -e "${BLUE}[10/10] Deployment Status${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if all critical components are ready
CRITICAL_CHECKS=("Bot Directory" "Python Virtual Environment" "Systemd Service File" "Service Running" "Environment File")
ALL_CRITICAL_PASS=true

for check in "${CRITICAL_CHECKS[@]}"; do
    # This is a simplified check - in production you'd track each check result
    :
done

if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null && [ -f "$BOT_DIR/.env" ]; then
    check_result "Deployment Status" "pass" "Bot is deployed and running"
else
    check_result "Deployment Status" "fail" "Bot is not fully deployed"
fi

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                     Health Check Summary                     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Checks Passed:  ${GREEN}$CHECKS_PASSED${NC}"
echo -e "Checks Failed:  ${RED}$CHECKS_FAILED${NC}"
echo -e "Warnings:       ${YELLOW}$WARNINGS${NC}"
echo ""

# Overall status
if [ $CHECKS_FAILED -eq 0 ]; then
    if [ $WARNINGS -eq 0 ]; then
        echo -e "Overall Status: ${GREEN}HEALTHY${NC} ✓"
        exit 0
    else
        echo -e "Overall Status: ${YELLOW}HEALTHY WITH WARNINGS${NC} ⚠"
        exit 0
    fi
else
    echo -e "Overall Status: ${RED}UNHEALTHY${NC} ✗"
    echo ""
    echo "Recommended Actions:"
    echo "  1. Review failed checks above"
    echo "  2. Check service logs: sudo journalctl -u $SERVICE_NAME -f"
    echo "  3. Verify configuration: cat $BOT_DIR/.env"
    echo "  4. Check AWS credentials: aws sts get-caller-identity"
    echo "  5. Restart service: sudo systemctl restart $SERVICE_NAME"
    exit 1
fi
