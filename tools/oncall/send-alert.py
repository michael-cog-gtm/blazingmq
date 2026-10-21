#!/usr/bin/env python3
"""Post the demo SRE alert for the priority-routing incident.

Usage:
  SLACK_WEBHOOK_URL=https://hooks.slack.com/... tools/oncall/send-alert.py [--print]

With --print (or no webhook URL) the Slack payload is printed instead of sent, so the
same text can be pasted into a channel by hand.
"""
import json, os, sys, urllib.request, datetime

REPO = os.environ.get("ALERT_REPO", "michael-cog-gtm/blazingmq")
BRANCH = os.environ.get("ALERT_BRANCH", "main")
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

title = ":rotating_light: SEV-2 Priority routing violation — standby consumers receiving live traffic"
fields = [
    ("Service", "BlazingMQ broker — priority queues (`bmq.prod.orders.*`)"),
    ("Signal", "`bmq.queue.consumer.standby_messages_delivered` > 0 for 15 min (expected 0)"),
    ("Magnitude", "standby consumers received *50.0%* of messages (3 of 6 per probe) across 4 clusters"),
    ("First seen", now),
    ("Repo / branch", f"{REPO} `{BRANCH}`"),
    ("Suspect window", "last 24h of changes to the broker message router"),
]
probe = (
    "probe: 1 producer, consumer A priority=10, consumer B priority=1, 6 messages\n"
    "  consumer A (primary)  received 3   order-1 order-3 order-5\n"
    "  consumer B (standby)  received 3   order-2 order-4 order-6   <-- should be 0\n"
    "impact: standby workers are processing live orders in parallel with primaries (duplicate processing risk)"
)
blocks = [
    {"type": "header", "text": {"type": "plain_text", "text": title[:150], "emoji": True}},
    {"type": "section", "fields": [{"type": "mrkdwn", "text": f"*{k}*\n{v}"} for k, v in fields]},
    {"type": "section", "text": {"type": "mrkdwn", "text": f"```{probe}```"}},
    {"type": "context", "elements": [{"type": "mrkdwn", "text": "Source: nightly routing-conformance probe · runbook: AGENTS.md → On-call rules · _simulated incident on the demo fork_"}]},
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
