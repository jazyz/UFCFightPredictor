#!/bin/bash
# Setup script for automatic UFC Fight Predictor retraining via launchd (macOS)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "================================================"
echo "UFC Fight Predictor - launchd Setup (macOS)"
echo "================================================"
echo ""

# Get the absolute path to this script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$SCRIPT_DIR"

PLIST_FILE="$PROJECT_DIR/com.ufcpredictor.autoretrain.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.ufcpredictor.autoretrain.plist"

echo "Project directory: $PROJECT_DIR"
echo "Plist file: $PLIST_FILE"
echo ""

# Check if plist file exists
if [ ! -f "$PLIST_FILE" ]; then
    echo -e "${RED}✗ Plist file not found: $PLIST_FILE${NC}"
    exit 1
fi

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"

# Menu
echo "Select an option:"
echo "1) Install/Update launchd job"
echo "2) Uninstall launchd job"
echo "3) Check job status"
echo "4) View logs"
echo "5) Test run now (manual)"
echo "6) Remove old cron job"
echo ""
read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        echo ""
        echo "Installing launchd job..."
        
        # Unload if already loaded
        launchctl unload "$INSTALLED_PLIST" 2>/dev/null
        
        # Copy plist file to LaunchAgents
        cp "$PLIST_FILE" "$INSTALLED_PLIST"
        
        # Load the job
        launchctl load "$INSTALLED_PLIST"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ launchd job installed successfully!${NC}"
            echo ""
            echo "Schedule: Monday and Friday at 2:00 AM"
            echo ""
            echo -e "${BLUE}Important: Unlike cron, launchd will run the job when your Mac wakes up if it was asleep at the scheduled time.${NC}"
            echo ""
            echo "Logs will be written to:"
            echo "  - $PROJECT_DIR/logs/launchd_output.log"
            echo "  - $PROJECT_DIR/logs/launchd_error.log"
            echo "  - $PROJECT_DIR/logs/auto_retrain_*.log"
        else
            echo -e "${RED}✗ Failed to install launchd job${NC}"
            exit 1
        fi
        ;;
        
    2)
        echo ""
        echo "Uninstalling launchd job..."
        
        if [ -f "$INSTALLED_PLIST" ]; then
            launchctl unload "$INSTALLED_PLIST"
            rm "$INSTALLED_PLIST"
            echo -e "${GREEN}✓ launchd job uninstalled${NC}"
        else
            echo -e "${YELLOW}⚠ Job not installed${NC}"
        fi
        ;;
        
    3)
        echo ""
        echo "Job status:"
        echo "================================================"
        
        if [ -f "$INSTALLED_PLIST" ]; then
            echo -e "${GREEN}✓ Job is installed${NC}"
            echo ""
            echo "Checking if loaded..."
            launchctl list | grep com.ufcpredictor.autoretrain
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Job is loaded and active${NC}"
            else
                echo -e "${YELLOW}⚠ Job is installed but not loaded${NC}"
                echo "Try running: launchctl load $INSTALLED_PLIST"
            fi
        else
            echo -e "${YELLOW}⚠ Job is not installed${NC}"
        fi
        
        echo ""
        echo "Next scheduled runs:"
        echo "  - Next Monday at 2:00 AM"
        echo "  - Next Friday at 2:00 AM"
        ;;
        
    4)
        echo ""
        echo "Recent logs:"
        echo "================================================"
        
        echo ""
        echo -e "${BLUE}=== Auto-retrain logs (most recent) ===${NC}"
        LATEST_LOG=$(ls -t "$PROJECT_DIR"/logs/auto_retrain_*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            echo "File: $LATEST_LOG"
            echo ""
            tail -20 "$LATEST_LOG"
        else
            echo "No auto-retrain logs found"
        fi
        
        echo ""
        echo -e "${BLUE}=== launchd output log ===${NC}"
        if [ -f "$PROJECT_DIR/logs/launchd_output.log" ]; then
            tail -20 "$PROJECT_DIR/logs/launchd_output.log"
        else
            echo "No launchd output log yet"
        fi
        
        echo ""
        echo -e "${BLUE}=== launchd error log ===${NC}"
        if [ -f "$PROJECT_DIR/logs/launchd_error.log" ]; then
            tail -20 "$PROJECT_DIR/logs/launchd_error.log"
        else
            echo "No launchd errors"
        fi
        ;;
        
    5)
        echo ""
        echo "Running auto-retrain manually..."
        cd "$PROJECT_DIR"
        "$PROJECT_DIR/.venv/bin/python" auto_retrain.py
        ;;
        
    6)
        echo ""
        echo "Removing old cron job..."
        
        # Check if cron job exists
        if crontab -l 2>/dev/null | grep -q "auto_retrain.py"; then
            # Remove the cron job
            crontab -l 2>/dev/null | grep -v "auto_retrain.py" | grep -v "UFC Fight Predictor Auto-Retrain" | crontab -
            echo -e "${GREEN}✓ Old cron job removed${NC}"
        else
            echo -e "${YELLOW}⚠ No cron job found${NC}"
        fi
        ;;
        
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo "================================================"
echo ""
echo "Useful commands:"
echo "  Check status:     ./setup_launchd.sh (choose option 3)"
echo "  View logs:        ./setup_launchd.sh (choose option 4)"
echo "  Test run:         ./setup_launchd.sh (choose option 5)"
echo "  Uninstall:        ./setup_launchd.sh (choose option 2)"
echo ""
