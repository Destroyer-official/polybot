# Systemd Management Guide

## Quick Reference

### Common Commands

```bash
# Service control
sudo systemctl start polybot      # Start the bot
sudo systemctl stop polybot       # Stop the bot
sudo systemctl restart polybot    # Restart the bot
sudo systemctl status polybot     # Check status

# Auto-start configuration
sudo systemctl enable polybot     # Enable auto-start on boot
sudo systemctl disable polybot    # Disable auto-start

# Logs
sudo journalctl -u polybot -f     # Follow live logs
sudo journalctl -u polybot -n 100 # Last 100 lines
sudo journalctl -u polybot --since today  # Today's logs
```

## Configuration Files

### Service File
**Location**: `/etc/systemd/system/polybot.service`

Key settings:
- `Restart=on-failure` - Only restart on crashes
- `RestartSec=30` - Wait 30 seconds between restarts
- `StartLimitBurst=10` - Max 10 restarts per hour
- `MemoryMax=2G` - Hard memory limit
- `CPUQuota=150%` - CPU limit (1.5 cores)

### Log Rotation
**Location**: `/etc/systemd/journald.conf.d/polybot.conf`

Key settings:
- `SystemMaxUse=1G` - Max 1GB total logs
- `MaxRetentionSec=30day` - Keep logs for 30 days
- `SystemMaxFileSize=100M` - Max 100MB per file

## Restart Behavior

### Automatic Restart
The service automatically restarts on failure with these limits:

- **Max restarts**: 10 per hour
- **Restart delay**: 30 seconds
- **Window**: 3600 seconds (1 hour)

If the service fails 10 times in 1 hour, systemd stops trying.

### Reset Restart Counter
```bash
sudo systemctl reset-failed polybot
```

### Check Restart Count
```bash
systemctl show polybot -p NRestarts
```

## Resource Limits

### Memory Limits
- **MemoryMax=2G**: Hard limit - process killed if exceeded
- **MemoryHigh=1.5G**: Soft limit - triggers memory pressure

### Check Memory Usage
```bash
systemctl status polybot | grep Memory
```

### CPU Limits
- **CPUQuota=150%**: Limits to 1.5 CPU cores

### Check CPU Usage
```bash
systemctl status polybot | grep CPU
```

## Log Management

### View Logs
```bash
# Live logs (follow mode)
sudo journalctl -u polybot -f

# Last N lines
sudo journalctl -u polybot -n 100

# Time-based
sudo journalctl -u polybot --since "1 hour ago"
sudo journalctl -u polybot --since "2024-01-01"
sudo journalctl -u polybot --since today

# Priority filtering
sudo journalctl -u polybot -p err    # Errors only
sudo journalctl -u polybot -p warning # Warnings and above

# Output formats
sudo journalctl -u polybot -o json-pretty
sudo journalctl -u polybot -o short-precise
```

### Export Logs
```bash
# Export to file
sudo journalctl -u polybot > polybot.log

# Export with time range
sudo journalctl -u polybot --since "2024-01-01" --until "2024-01-31" > january.log
```

### Disk Usage
```bash
# Check total log disk usage
sudo journalctl --disk-usage

# Vacuum old logs
sudo journalctl --vacuum-time=7d    # Keep last 7 days
sudo journalctl --vacuum-size=500M  # Keep last 500MB

# Rotate logs manually
sudo journalctl --rotate
```

## Troubleshooting

### Service Won't Start

1. **Check status**:
   ```bash
   sudo systemctl status polybot
   ```

2. **Check recent logs**:
   ```bash
   sudo journalctl -u polybot -n 50
   ```

3. **Verify environment file**:
   ```bash
   ls -la /home/ubuntu/polybot/.env
   cat /home/ubuntu/polybot/.env  # Check variables are set
   ```

4. **Test manually**:
   ```bash
   cd /home/ubuntu/polybot
   source venv/bin/activate
   python bot.py
   ```

### Service Keeps Restarting

1. **Check restart count**:
   ```bash
   systemctl show polybot -p NRestarts
   ```

2. **View crash logs**:
   ```bash
   sudo journalctl -u polybot --since "10 minutes ago"
   ```

3. **Check for resource limits**:
   ```bash
   systemctl status polybot | grep -E "Memory|CPU"
   ```

4. **Reset and monitor**:
   ```bash
   sudo systemctl reset-failed polybot
   sudo systemctl start polybot
   sudo journalctl -u polybot -f
   ```

### High Memory Usage

1. **Check current usage**:
   ```bash
   systemctl status polybot | grep Memory
   ```

2. **Adjust limits** (edit service file):
   ```bash
   sudo nano /etc/systemd/system/polybot.service
   # Change MemoryMax and MemoryHigh
   sudo systemctl daemon-reload
   sudo systemctl restart polybot
   ```

### Logs Not Rotating

1. **Check journald status**:
   ```bash
   sudo systemctl status systemd-journald
   ```

2. **Verify configuration**:
   ```bash
   cat /etc/systemd/journald.conf.d/polybot.conf
   ```

3. **Restart journald**:
   ```bash
   sudo systemctl restart systemd-journald
   ```

4. **Manual rotation**:
   ```bash
   sudo journalctl --rotate
   sudo journalctl --vacuum-time=30d
   ```

## Monitoring

### Health Check Script
Run the health check script:
```bash
cd /home/ubuntu/polybot/deployment
bash health_check.sh
```

### Key Metrics to Monitor

1. **Service Status**:
   ```bash
   systemctl is-active polybot
   ```

2. **Restart Count**:
   ```bash
   systemctl show polybot -p NRestarts
   ```

3. **Memory Usage**:
   ```bash
   systemctl status polybot | grep Memory
   ```

4. **CPU Usage**:
   ```bash
   systemctl status polybot | grep CPU
   ```

5. **Uptime**:
   ```bash
   systemctl show polybot -p ActiveEnterTimestamp
   ```

6. **Recent Errors**:
   ```bash
   sudo journalctl -u polybot --since "1 hour ago" -p err | wc -l
   ```

### Automated Monitoring with Cron

Add to crontab (`crontab -e`):
```bash
# Health check every 5 minutes
*/5 * * * * /home/ubuntu/polybot/deployment/health_check.sh >> /home/ubuntu/polybot/logs/health.log 2>&1

# Daily log summary
0 0 * * * sudo journalctl -u polybot --since "24 hours ago" > /home/ubuntu/polybot/logs/daily_$(date +\%Y\%m\%d).log
```

## Maintenance

### Update Service Configuration

1. **Edit service file**:
   ```bash
   sudo nano /etc/systemd/system/polybot.service
   ```

2. **Reload systemd**:
   ```bash
   sudo systemctl daemon-reload
   ```

3. **Restart service**:
   ```bash
   sudo systemctl restart polybot
   ```

### Update Log Configuration

1. **Edit journald config**:
   ```bash
   sudo nano /etc/systemd/journald.conf.d/polybot.conf
   ```

2. **Restart journald**:
   ```bash
   sudo systemctl restart systemd-journald
   ```

### Backup Configuration

```bash
# Backup service file
sudo cp /etc/systemd/system/polybot.service ~/polybot-service-backup.service

# Backup journald config
sudo cp /etc/systemd/journald.conf.d/polybot.conf ~/polybot-journald-backup.conf
```

## Emergency Procedures

### Stop Bot Immediately
```bash
sudo systemctl stop polybot
```

### Prevent Auto-Restart
```bash
sudo systemctl disable polybot
sudo systemctl stop polybot
```

### Emergency Rollback
```bash
cd /home/ubuntu/polybot
git reset --hard [PREVIOUS_COMMIT]
sudo systemctl restart polybot
```

### View Crash Dumps
```bash
# Check for core dumps
coredumpctl list
coredumpctl info [PID]
```

## Performance Tuning

### Increase Memory Limit
```bash
sudo nano /etc/systemd/system/polybot.service
# Change: MemoryMax=4G
sudo systemctl daemon-reload
sudo systemctl restart polybot
```

### Increase CPU Limit
```bash
sudo nano /etc/systemd/system/polybot.service
# Change: CPUQuota=200%
sudo systemctl daemon-reload
sudo systemctl restart polybot
```

### Adjust Restart Behavior
```bash
sudo nano /etc/systemd/system/polybot.service
# Change: StartLimitBurst=20 (allow more restarts)
# Change: RestartSec=60 (longer delay)
sudo systemctl daemon-reload
```

## Best Practices

1. **Always check logs before restarting**:
   ```bash
   sudo journalctl -u polybot -n 100
   sudo systemctl restart polybot
   ```

2. **Monitor after changes**:
   ```bash
   sudo systemctl restart polybot
   sudo journalctl -u polybot -f
   ```

3. **Regular health checks**:
   ```bash
   bash /home/ubuntu/polybot/deployment/health_check.sh
   ```

4. **Keep logs manageable**:
   ```bash
   sudo journalctl --vacuum-time=30d
   ```

5. **Document changes**:
   - Keep notes of configuration changes
   - Backup configs before modifying
   - Test changes in non-production first

## Related Files

- Service file: `deployment/polybot.service`
- Journald config: `deployment/journald-polybot.conf`
- Setup script: `deployment/setup_systemd.sh`
- Health check: `deployment/health_check.sh`
- Deployment: `deployment/deploy_systemd_config.ps1`
- Full README: `deployment/SYSTEMD_README.md`
