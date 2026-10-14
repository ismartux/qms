#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  IIPL Platform: Merging DCC with QMS"
echo "  Target Host: qms.ismartux.com"
echo "  DCC Portal: https://qms.ismartux.com/dcc/"
echo "========================================================"

echo "=== [1/5] Updating Gunicorn Service for DCC Backend ==="
sudo cp /home/mrsingh29/apps/qms/dcc/dcc-gunicorn.service /etc/systemd/system/dcc-gunicorn.service
sudo systemctl daemon-reload
sudo systemctl restart dcc-gunicorn.service
sudo systemctl restart qms-gunicorn.service

echo "=== [2/5] Disabling standalone dcc.ismartux.com site from sites-enabled ==="
if [ -L /etc/nginx/sites-enabled/dcc ] || [ -f /etc/nginx/sites-enabled/dcc ]; then
    sudo rm -f /etc/nginx/sites-enabled/dcc
fi

echo "=== [3/5] Updating qms.ismartux.com in Nginx ==="
sudo cp /home/mrsingh29/apps/qms/nginx-qms.conf /etc/nginx/sites-available/qms
sudo ln -sf /etc/nginx/sites-available/qms /etc/nginx/sites-enabled/qms

echo "=== [4/5] Testing and Reloading Nginx ==="
sudo nginx -t
sudo systemctl reload nginx

echo "=== [5/5] Checking Services Status ==="
sudo systemctl is-active dcc-gunicorn.service
sudo systemctl is-active qms-gunicorn.service
sudo systemctl is-active nginx

echo "========================================================"
echo "  Merge & Deployment Completed Successfully!"
echo "  QMS Portal: https://qms.ismartux.com"
echo "  DCC Portal: https://qms.ismartux.com/dcc/"
echo "========================================================"

