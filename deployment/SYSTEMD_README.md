# Systemd Configuration for Autonomous Operation

This directory contains systemd configuration files for running the Polymarket Bot as a fully autonomous service.

## Features

### 1. Automatic Restart on Failure
- **Max restarts**: 10 per hour
- **Restart delay**: 30 seconds between attempts
- **Restart policy**: Only on failure (not on clean shutdown)

### 2. Graceful Shutdown
- **Timeout**: 60 seconds to complete pending operations
- **Signal**: SIGTERM for graceful shutdown
- **Kill mode**: Mixed (graceful then forceful)

### 3. Environment Variable Loading
- Loads from `/home/ubuntu/polybot/.env`
- Sets `PYTHONUNBUFFERED=1` for real-time logging
- Configures PATH for virtual environment

### 4. Automatic Log Rotation
- **Max disk usage**: 1GB total
- **Retention**: 30 days
- **Compression**: Enabled for logs older than 1 day
- **Max file size**: 100MB per file
- **Storage**: Persistent (survives reboots)

### 5. Resource Limits
- **Memory max**: 2GB (hard limit)
- **Memory high**: 1.5GB (soft limit, triggers pressure)
- **CPU quota**: 150% (1.5 cores)
- **Max tasks**: 512 concurrent tasks

### 6. Security Hardening
- No new privileges
- Protected system directories
- Protected home directory (read-only)
- Private temporary directory
- Protected kernel tunables
- Restricted namespaces and realtime scheduling

## Installation

### Quick Setup

```bash
cd deployment
sudo bash setup_systemd.sh
```

### Manual Setup

1. **Copy service file**:
   ```bash
   sudo cp polybot.service /etc/systemd/system/
   ```

2. **Copy journald config**:
   ```bash
   sudo mkdir -p /etc/systemd/journald.conf.d
   sudo cp journald-polybot.conf /etc/systemd/journald.conf.d/polybot.conf
   ```

3. **Create required directories**:
   ```bash
   mkdir -p /home/ubuntu/polybot/{logs,data,state}
   ```

4. **Reload systemd**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart systemd-journald
   ```

5. **Enable and start service**:
   ```bash
   sudo systemctl enable polybot
   sudo systemctl start polybot
   ```

## Usage

### Service Management

```bash
# Start the bot
sudo systemctl start polybot

# Stop the bot
sudo systemctl stop polybot

# Restart the bot
sudo systemctl restart polybot

# Check status
sudo systemctl status polybot

# Enable auto-start on boot
sudo systemctl enable polybot

# Disable auto-start
sudo systemctl disable polybot
```

### Log Management

```bash
# View live logs
sudo journalctl -u polybot -f

# View logs from today
sudo journalctl -u polybot --since today

# View last 100 lines
sudo journalctl -u polybot -n 100

# View logs with timestamps
sudo journalctl -u polybot -o short-precise

# View logs in JSON format
sudo journalctl -u polybot -o json-pretty

# Export logs to file
sudo journalctl -u polybot > polybot.log

# Check disk usage
sudo journalctl --disk-usage

# Manually rotate logs
sudo journalctl --rotate

# Vacuum old logs (keep last 7 days)
sudo journalctl --vacuum-time=7d

# Vacuum by size (keep last 500MB)
sudo journalctl --vacuum-size=500M
```

### Monitoring

```bash
# Check restart count
systemctl show polybot -p NRestarts

# Check memory usage
systemctl status polybot | grep Memory

# Check CPU usage
systemctl status polybot | grep CPU

# Check uptime
systemctl show polybot -p ActiveEnterTimestamp

# Check if service is enabled
systemctl is-enabled polybot

# Check if service is active
systemctl is-active polybot
```

## Configuration Details

### Restart Policy

The service is configured to restart automatically on failure with the following limits:

- **StartLimitIntervalSec**: 3600 (1 hour window)
- **StartLimitBurst**: 10 (max 10 restarts in the window)
- **RestartSec**: 30 (wait 30 seconds between restarts)

If the service fails 10 times within 1 hour, systemd will stop trying to restart it. You can manually reset the counter with:

```bash
sudo systemctl reset-failed polybot
sudo systemctl start polybot
```

### Resource Limits

Resource limits prevent the bot from consuming excessive system resources:

- **MemoryMax=2G**: Hard limit - service is killed if exceeded
- **MemoryHigh=1.5G**: Soft limit - triggers memory pressure
- **CPUQuota=150%**: Limits to 1.5 CPU cores
- **TasksMax=512**: Limits concurrent tasks/threads

To adjust limits, edit `/etc/systemd/system/polybot.service` and reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart polybot
```

### Log Rotation

Logs are automatically rotated by systemd-journald based on:

- **Time**: Logs older than 30 days are deleted
- **Size**: Total logs limited to 1GB
- **Free space**: Keeps at least 2GB free on disk
- **Compression**: Logs older than 1 day are compressed

Configuration is in `/etc/systemd/journald.conf.d/polybot.conf`.

## Troubleshooting

### Service won't start

```bash
# Check for errors
sudo journalctl -u polybot -n 50

# Check service status
sudo systemctl status polybot

# Verify environment file exists
ls -la /home/ubuntu/polybot/.env

# Verify Python virtual environment
ls -la /home/ubuntu/polybot/venv/bin/python

# Test manually
cd /home/ubuntu/polybot
source venv/bin/activate
python bot.py
```

### Service keeps restarting

```bash
# Check restart count
systemctl show polybot -p NRestarts

# View recent failures
sudo journalctl -u polybot --since "10 minutes ago"

# Check if hitting resource limits
systemctl status polybot | grep -E "Memory|CPU"

# Reset restart counter
sudo systemctl reset-failed polybot
```

### Logs not rotating

```bash
# Check journald status
sudo systemctl status systemd-journald

# Verify configuration
cat /etc/systemd/journald.conf.d/polybot.conf

# Manually trigger rotation
sudo journalctl --rotate

# Check disk usage
sudo journalctl --disk-usage
```

### High memory usage

```bash
# Check current usage
systemctl status polybot | grep Memory

# View memory over time
sudo journalctl -u polybot | grep "Memory usage"

# Adjust limits if needed
sudo nano /etc/systemd/system/polybot.service
# Change MemoryMax and MemoryHigh values
sudo systemctl daemon-reload
sudo systemctl restart polybot
```

## Autonomous Operation Checklist

- [x] Auto-restart on failure (max 10 per hour)
- [x] 30-second restart delay
- [x] Environment variable loading from .env file
- [x] Automatic log rotation (30 days, 1GB max)
- [x] Resource limits (2GB memory, 150% CPU)
- [x] Graceful shutdown (60-second timeout)
- [x] Security hardening (restricted permissions)
- [x] Persistent storage for logs, data, and state
- [x] Auto-start on boot (when enabled)

## Next Steps

After setting up systemd:

1. **Verify environment file**: Ensure `/home/ubuntu/polybot/.env` contains all required variables
2. **Test startup**: Run `sudo systemctl start polybot` and check logs
3. **Monitor for 24 hours**: Watch for crashes or resource issues
4. **Enable auto-start**: Run `sudo systemctl enable polybot` once stable
5. **Set up monitoring**: Configure external monitoring for alerts

## References

- Task: 14.2 Configure systemd for full autonomy
- Requirements: 7.1 (Systemd Service)
- Design: Section 9.1 (Deployment Architecture)
