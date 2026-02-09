#!/bin/bash
# Deploy Perfect LLM Decision Engine V2 to AWS

echo "========================================="
echo "DEPLOYING LLM DECISION ENGINE V2"
echo "========================================="
echo ""

echo "1. Uploading new V2 engine..."
scp -i money.pem src/llm_decision_engine_v2.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/

echo ""
echo "2. Uploading updated strategy..."
scp -i money.pem src/fifteen_min_crypto_strategy.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/

echo ""
echo "3. Uploading updated orchestrator..."
scp -i money.pem src/main_orchestrator.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/

echo ""
echo "4. Clearing Python cache..."
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"

echo ""
echo "5. Restarting bot..."
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot"

echo ""
echo "6. Waiting for startup..."
sleep 5

echo ""
echo "7. Checking status..."
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot --no-pager | head -15"

echo ""
echo "========================================="
echo "DEPLOYMENT COMPLETE!"
echo "========================================="
echo ""
echo "Monitor logs with:"
echo "ssh -i money.pem ubuntu@35.76.113.47 \"sudo journalctl -u polybot -f\""
echo ""
echo "Check for V2 engine:"
echo "ssh -i money.pem ubuntu@35.76.113.47 \"sudo journalctl -u polybot -n 50 --no-pager | grep 'V2\\|PERFECT\\|DIRECTIONAL'\""
