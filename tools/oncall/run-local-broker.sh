#!/usr/bin/env bash
# Start a single-node BlazingMQ broker on tcp://localhost:30114 using the single-node config.
# Usage: tools/oncall/run-local-broker.sh [start|stop]
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BRKR=$ROOT/build/blazingmq/src/applications/bmqbrkr/bmqbrkr.tsk
CFG=${BMQ_LOCAL_CONFIG:-/tmp/bmq-local-config}
RUN=/tmp/bmq-local-run
case "${1:-start}" in
  stop) pkill -x bmqbrkr.tsk || true; echo "broker stopped"; exit 0;;
esac
[ -x "$BRKR" ] || { echo "broker not built: $BRKR (see AGENTS.md)"; exit 1; }
sudo mkdir -p /var/local/bmq/logs /var/local/bmq/storage/archive && sudo chown -R "$(id -u)" /var/local/bmq
rm -rf "$CFG" && cp -r "$ROOT/docker/single-node/config" "$CFG"
sed -i 's/"hostName": "earth"/"hostName": "localhost"/' "$CFG/bmqbrkrcfg.json"
pkill -x bmqbrkr.tsk 2>/dev/null || true; sleep 1
mkdir -p "$RUN" && cd "$RUN" && nohup "$BRKR" "$CFG" > "$RUN/broker.out" 2>&1 &
for i in $(seq 1 30); do sleep 1; if ss -ltn 2>/dev/null | grep -q ':30114 '; then echo "broker listening on tcp://localhost:30114 (logs: /var/local/bmq/logs, stdout: $RUN/broker.out)"; exit 0; fi; done
echo "broker did not start; see $RUN/broker.out"; exit 1
