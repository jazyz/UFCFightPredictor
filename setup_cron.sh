#!/bin/bash
# Setup script for automatic UFC Fight Predictor retraining via cron

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "UFC Fight Predictor - Cron Job Setup"
echo "================================================"
echo ""

# Get the absolute path to this script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$SCRIPT_DIR"

echo "Project directory: $PROJECT_DIR"
echo ""

# Get Python path
PYTHON_PATH=$(which python3)
if [ -z "$PYTHON_PATH" ]; then
    PYTHON_PATH=$(which python)
fi

echo "Python path: $PYTHON_PATH"
echo ""

# Check if virtual environment exists
if [ -d "$PROJECT_DIR/.venv" ]; then
    PYTHON_PATH="$PROJECT_DIR/.venv/bin/python"
    echo -e "${GREEN}✓ Using virtual environment${NC}"
elif [ -d "$PROJECT_DIR/venv" ]; then
    PYTHON_PATH="$PROJECT_DIR/venv/bin/python"
    echo -e "${GREEN}✓ Using virtual environment${NC}"
else
    echo -e "${YELLOW}⚠ No virtual environment found, using system Python${NC}"
fi

echo "Python interpreter: $PYTHON_PATH"
echo ""

# Schedule options
echo "Select retraining schedule:"
echo "1) Weekly on Monday at 2 AM (recommended)"
echo "2) Twice per week (Monday and Friday at 2 AM)"
echo "3) Daily at 2 AM"
echo "4) Custom schedule"
echo "5) View current cron jobs only"
echo ""
read -p "Enter choice [1-5]: " schedule_choice

case $schedule_choice in
    1)
        CRON_SCHEDULE="0 2 * * 1"
        SCHEDULE_DESC="Weekly on Monday at 2 AM"
        ;;
    2)
        CRON_SCHEDULE="0 2 * * 1,5"
        SCHEDULE_DESC="Monday and Friday at 2 AM"
        ;;
    3)
        CRON_SCHEDULE="0 2 * * *"
        SCHEDULE_DESC="Daily at 2 AM"
        ;;
    4)
        echo ""
        echo "Cron format: minute hour day_of_month month day_of_week"
        echo "Example: '0 2 * * 1' = Monday at 2 AM"
        read -p "Enter custom cron schedule: " CRON_SCHEDULE
        SCHEDULE_DESC="Custom: $CRON_SCHEDULE"
        ;;
    5)
        echo ""
        echo "Current cron jobs:"
        crontab -l 2>/dev/null | grep -v "^#" || echo "No cron jobs found"
        echo ""
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo "================================================"
echo "Configuration Summary"
echo "================================================"
echo "Schedule: $SCHEDULE_DESC"
echo "Python: $PYTHON_PATH"
echo "Project: $PROJECT_DIR"
echo "Script: auto_retrain.py"
echo ""

# Create the cron command
CRON_CMD="cd $PROJECT_DIR && $PYTHON_PATH auto_retrain.py >> logs/cron_output.log 2>&1"

# Create log directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

echo "Cron command to be added:"
echo "$CRON_SCHEDULE $CRON_CMD"
echo ""

read -p "Do you want to add this cron job? [y/N]: " confirm

if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Backup existing crontab
crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null
echo -e "${GREEN}✓ Backed up existing crontab${NC}"

# Add the new cron job
(crontab -l 2>/dev/null; echo "# UFC Fight Predictor Auto-Retrain") | crontab -
(crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $CRON_CMD") | crontab -

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Cron job added successfully!${NC}"
    echo ""
    echo "Your auto-retraining is now scheduled for: $SCHEDULE_DESC"
    echo ""
    echo "Useful commands:"
    echo "  View cron jobs:    crontab -l"
    echo "  Edit cron jobs:    crontab -e"
    echo "  Remove cron jobs:  crontab -r"
    echo "  View logs:         tail -f $PROJECT_DIR/logs/cron_output.log"
    echo ""
    echo "To test manually:"
    echo "  cd $PROJECT_DIR && python auto_retrain.py"
else
    echo -e "${RED}✗ Failed to add cron job${NC}"
    exit 1
fi
