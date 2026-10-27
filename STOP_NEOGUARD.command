#!/bin/bash
cd "$(dirname "$0")"
if [ -f .neoguard_backend.pid ]; then
  PID="$(cat .neoguard_backend.pid)"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    echo "NeoGuard backend stopped."
  else
    echo "NeoGuard backend was not running."
  fi
  rm -f .neoguard_backend.pid
else
  echo "No NeoGuard backend PID file found."
fi
read -r -p "Press Return to close..."
