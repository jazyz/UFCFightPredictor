#!/usr/bin/env bash
# The launchd entry point: retrain, then publish the site data only if the retrain
# succeeded. Arguments are passed through to auto_retrain.py.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"

# launchd starts with a minimal PATH, so the interpreter is resolved explicitly rather
# than left to `python3` (which would find /usr/bin/python3 and none of the deps).
# Order: $UFC_PYTHON, the repo venv, the pinned interpreter that has the deps.
resolve_python() {
    local candidate
    for candidate in "${UFC_PYTHON:-}" "$REPO/.venv/bin/python" /Users/aalex_xuu/anaconda3/bin/python3; do
        [ -n "$candidate" ] && [ -x "$candidate" ] || continue
        if "$candidate" -c 'import pandas, lightgbm, sklearn, bs4, requests' 2>/dev/null; then
            echo "$candidate"
            return 0
        fi
        echo "run_scheduled.sh: $candidate is missing pipeline dependencies; skipping" >&2
    done
    return 1
}

if ! PY="$(resolve_python)"; then
    echo "run_scheduled.sh: no usable Python found. Set UFC_PYTHON to an interpreter" >&2
    echo "  with the requirements.txt deps, or create $REPO/.venv." >&2
    exit 1
fi
echo "run_scheduled.sh: using $PY"

"$PY" "$REPO/auto_retrain.py" "$@"
"$PY" "$REPO/publish_site.py"
