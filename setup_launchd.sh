#!/usr/bin/env bash
# Installs the Mon/Fri 2:00 AM auto-retrain launchd job documented in CLAUDE.md.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.ufcpredictor.autoretrain"
TEMPLATE="$REPO/$LABEL.plist.template"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(id -u)"

if [ ! -f "$TEMPLATE" ]; then
    echo "Template not found: $TEMPLATE" >&2
    exit 1
fi

echo "This will install launchd job '$LABEL':"
echo "  runs:  $REPO/.venv/bin/python $REPO/auto_retrain.py"
echo "  when:  Monday & Friday 02:00"
echo "  plist: $PLIST"
printf "Proceed? [y/N] "
read -r answer
case "$answer" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Aborted."; exit 0 ;;
esac

mkdir -p "$REPO/logs" "$HOME/Library/LaunchAgents"
sed "s|__REPO__|$REPO|g" "$TEMPLATE" > "$PLIST"

# Idempotent: bootout any existing copy of the job before (re)installing.
if launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1; then
    echo "Job already installed; removing old copy first."
    launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null \
        || launchctl unload "$PLIST" 2>/dev/null \
        || true
fi

# Keep bootstrap's stderr: a real failure (bad plist, sandbox denial) must not
# be misread as "old macOS without the bootstrap subcommand".
if BOOT_ERR=$(launchctl bootstrap "gui/$UID_NUM" "$PLIST" 2>&1); then
    echo "Installed via 'launchctl bootstrap'."
elif printf '%s' "$BOOT_ERR" | grep -qi 'Unknown subcommand'; then
    launchctl load "$PLIST"
    echo "Installed via 'launchctl load'."
else
    echo "launchctl bootstrap failed: $BOOT_ERR" >&2
    exit 1
fi

echo
echo "Status check: launchctl print gui/$UID_NUM/$LABEL | head"
launchctl print "gui/$UID_NUM/$LABEL" | head || true
echo
echo "To uninstall: launchctl bootout gui/$UID_NUM/$LABEL  (older macOS: launchctl unload $PLIST)"
