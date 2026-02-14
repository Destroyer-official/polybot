#!/bin/bash
# Health check script for Polymarket Bot
# Can be used by monitoring systems or cron jobs

SERVICE_NAME="polybot"
ALERT_EMAIL=""  # Set this to receive email alerts
MAX_MEMORY_MB=1800  # Alert if memory exceeds 1.8GB
MAX_RESTARTS=5  # Alert if restart count exceeds this

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if service is running
is_active=$(systemctl is-active $SERVICE_NAME)
if [ "$is_active" != "active" ]; then
    echo -e "${RED}✗ Service is not active: $is_active${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Service is active${NC}"

# Check restart count
restart_count=$(systemctl show $SERVICE_NAME -p NRestarts --value)
if [ "$restart_count" -gt "$MAX_RESTARTS" ]; then
    echo -e "${YELLOW}⚠ High restart count: $restart_count${NC}"
else
    echo -e "${GREEN}✓ Restart count: $restart_count${NC}"
fi

# Check memory usage
memory_bytes=$(systemctl show $SERVICE_NAME -p MemoryCurrent --value)
if [ "$memory_bytes" != "[not set]" ] && [ "$memory_bytes" -gt 0 ]; then
    memory_mb=$((memory_bytes / 1024 / 1024))
    if [ "$memory_mb" -gt "$MAX_MEMORY_MB" ]; then
        echo -e "${YELLOW}⚠ High memory usage: ${memory_mb}MB${NC}"
    else
        echo -e "${GREEN}✓ Memory usage: ${memory_mb}MB${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Memory usage: Unknown${NC}"
fi

# Check CPU usage
cpu_usage=$(systemctl show $SERVICE_NAME -p CPUUsageNSec --value)
if [ "$cpu_usage" != "[not set]" ] && [ "$cpu_usage" -gt 0 ]; then
    echo -e "${GREEN}✓ CPU usage tracked${NC}"
else
    echo -e "${YELLOW}⚠ CPU usage: Unknown${NC}"
fi

# Check uptime
active_since=$(systemctl show $SERVICE_NAME -p ActiveEnterTimestamp --value)
if [ -n "$active_since" ]; then
    echo -e "${GREEN}✓ Active since: $active_since${NC}"
fi

# Check recent errors
error_count=$(journalctl -u $SERVICE_NAME --since "1 hour ago" -p err | wc -l)
if [ "$error_count" -gt 0 ]; then
    echo -e "${YELLOW}⚠ Errors in last hour: $error_count${NC}"
    echo "Recent errors:"
    journalctl -u $SERVICE_NAME --since "1 hour ago" -p err --no-pager | tail -5
else
    echo -e "${GREEN}✓ No errors in last hour${NC}"
fi

# Check log disk usage
log_size=$(journalctl --disk-usage | grep -oP '\d+\.\d+[GM]' | head -1)
echo -e "${GREEN}✓ Log disk usage: $log_size${NC}"

# Overall health status
echo ""
if [ "$is_active" = "active" ] && [ "$restart_count" -le "$MAX_RESTARTS" ]; then
    echo -e "${GREEN}Overall Status: HEALTHY${NC}"
    exit 0
else
    echo -e "${RED}Overall Status: UNHEALTHY${NC}"
    exit 1
fi
