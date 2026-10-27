#!/bin/bash
set -u
cd "$(dirname "$0")"
ROOT="$PWD"
PYTHON_BIN="$(command -v python3)"
if [ -z "$PYTHON_BIN" ]; then
  osascript -e 'display dialog "Python 3 was not found. Install/use your Python or Anaconda environment first." buttons {"OK"} default button "OK"'
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import flask' >/dev/null 2>&1; then
  echo "Missing Python packages. Run: python3 -m pip install flask"
  read -r -p "Press Return to close..."
  exit 1
fi
if [ -f .neoguard_backend.pid ] && kill -0 "$(cat .neoguard_backend.pid)" 2>/dev/null; then
  echo "NeoGuard backend already appears to be running."
else
  PYTHONPATH="$ROOT:$ROOT/dashboard" "$PYTHON_BIN" app.py > neoguard_backend.log 2>&1 &
  echo $! > .neoguard_backend.pid
  sleep 1
fi
# The dashboard is now a tabbed web app served by the backend.
sleep 1
open "http://127.0.0.1:5001" 2>/dev/null || xdg-open "http://127.0.0.1:5001" 2>/dev/null || echo "Open http://127.0.0.1:5001 in your browser."
echo "NeoGuard is running at http://127.0.0.1:5001  (run STOP_NEOGUARD.command to stop)"
