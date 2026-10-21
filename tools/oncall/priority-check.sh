#!/usr/bin/env bash
# Starts a PRIMARY consumer (priority 10) and a STANDBY consumer (priority 1) on one priority queue,
# posts N messages, and reports how many each consumer received. Correct behaviour: standby = 0.
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TOOL=${TOOL:-$ROOT/build/blazingmq/src/applications/bmqtool/bmqtool.tsk}
URI=${URI:-bmq://bmq.test.mem.priority/oncall-check-$$}
N=${N:-6}
OUT=${OUT:-/tmp/prio-check}; rm -rf "$OUT"; mkdir -p "$OUT"
consumer() { # name priority
  ( printf 'start\nopen uri="%s" flags="read" consumerPriority=%s\n' "$URI" "$2"; sleep $((N+8)); printf 'close uri="%s"\nstop\nquit\n' "$URI" ) \
    | "$TOOL" --dumpmsg --confirmmsg -v info > "$OUT/$1.log" 2>&1 & echo $!
}
P=$(consumer primary 10); sleep 2
S=$(consumer standby 1);  sleep 2
( printf 'start\nopen uri="%s" flags="write,ack"\n' "$URI"; for i in $(seq 1 $N); do printf 'post uri="%s" payload=["order-%s"]\n' "$URI" "$i"; sleep 0.3; done; sleep 2; printf 'close uri="%s"\nstop\nquit\n' "$URI" ) \
  | "$TOOL" -v info > "$OUT/producer.log" 2>&1
wait $P $S 2>/dev/null
pc=$(grep -c "order-" "$OUT/primary.log"); sc=$(grep -c "order-" "$OUT/standby.log")
echo "posted=$N  primary(priority 10) received=$pc  standby(priority 1) received=$sc"
if [ "$sc" -eq 0 ] && [ "$pc" -eq "$N" ]; then echo "PASS: standby stayed idle"; exit 0; else echo "FAIL: standby received live traffic"; exit 1; fi
