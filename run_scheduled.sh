#!/usr/bin/env bash
# The launchd entry point: retrain, then publish the site data only if the retrain
# succeeded. Arguments are passed through to auto_retrain.py.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
PY="$REPO/.venv/bin/python"

"$PY" "$REPO/auto_retrain.py" "$@"
"$PY" "$REPO/publish_site.py"
