#!/usr/bin/env bash
set -euo pipefail
log=$(mktemp)
port=${CLAIMS_SMOKE_PORT:-8512}
python -m streamlit run app/Home.py --server.headless=true --server.address=127.0.0.1 --server.port="$port" >"$log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; rm -f "$log"' EXIT
for attempt in $(seq 1 30); do
    if ! kill -0 "$pid" 2>/dev/null; then
        cat "$log"
        exit 1
    fi
    if curl -fsS "http://127.0.0.1:$port/_stcore/health" 2>/dev/null | grep -qx ok; then
        curl -fsS "http://127.0.0.1:$port/" > /dev/null
        exit 0
    fi
    sleep 1
done
cat "$log"
exit 1
