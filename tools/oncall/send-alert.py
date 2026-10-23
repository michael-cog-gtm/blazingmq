#!/usr/bin/env python3
"""Post the demo SRE alert for the priority-routing incident.

Usage:
  SLACK_WEBHOOK_URL=https://hooks.slack.com/... tools/oncall/send-alert.py [--print]

With --print (or no webhook URL) the Slack payload is printed instead of sent, so the
same text can be pasted into a channel by hand.
"""
import json, os, sys, urllib.request, datetime

REPO = os.environ.get("ALERT_REPO", "michael-cog-gtm/blazingmq")
E = os.environ.get
POSTED = int(E("ALERT_POSTED", "6")); PRIM = int(E("ALERT_PRIMARY", "3")); STBY = int(E("ALERT_STANDBY", "3"))
ORD_P = E("ALERT_ORDERS_PRIMARY", "order-1 order-3 order-5"); ORD_S = E("ALERT_ORDERS_STANDBY", "order-2 order-4 order-6")
SOURCE = E("ALERT_SOURCE", "nightly routing-conformance probe"); QUEUE = E("ALERT_QUEUE", "bmq.prod.orders.*")
SHARE = (100.0 * STBY / POSTED) if POSTED else 0.0
BRANCH = os.environ.get("ALERT_BRANCH", "main")
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

title = ":rotating_light: SEV-2 Priority routing violation — standby consumers receiving live traffic"
fields = [
    ("Service", f"BlazingMQ broker — priority queues (`{QUEUE}`)"),
    ("Signal", "`bmq.queue.consumer.standby_messages_delivered` > 0 for 15 min (expected 0)"),
    ("Magnitude", f"standby consumers received *{SHARE:.1f}%* of messages ({STBY} of {POSTED} in the window) across 4 clusters"),
    ("First seen", now),
    ("Repo / branch", f"{REPO} `{BRANCH}`"),
    ("Suspect window", "last 24h of changes to the broker message router"),
]
probe = (
    f"probe: 1 producer, consumer A priority=10, consumer B priority=1, {POSTED} messages\n"
    f"  consumer A (primary)  received {PRIM}   {ORD_P}\n"
    f"  consumer B (standby)  received {STBY}   {ORD_S}   <-- should be 0\n"
    "impact: standby workers are processing live orders in parallel with primaries (duplicate processing risk)"
)
blocks = [
    {"type": "header", "text": {"type": "plain_text", "text": title[:150], "emoji": True}},
    {"type": "section", "fields": [{"type": "mrkdwn", "text": f"*{k}*\n{v}"} for k, v in fields]},
    {"type": "section", "text": {"type": "mrkdwn", "text": f"```{probe}```"}},
    {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Source: {SOURCE} · runbook: AGENTS.md → On-call rules · _simulated incident on the demo fork_"}]},
]
payload = {"text": title, "blocks": blocks}
url = os.environ.get("SLACK_WEBHOOK_URL")
if "--print" in sys.argv or not url:
    print(title)
    for k, v in fields:
        print(f"{k}: {v}")
    print(probe)
    sys.exit(0)
req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=15) as r:
    print("posted:", r.status)
