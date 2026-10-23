# Working in this repository (notes for Devin and other agents)

BlazingMQ is a C++ distributed message queue (broker `bmqbrkr`, CLI `bmqtool`, client libraries).
This fork is used for on-call and engineering demos; the rules below keep sessions fast and honest.

## Build (Ubuntu)

- Prerequisites are those in `docker/Dockerfile` plus **CMake >= 3.24** (`sudo pip3 install 'cmake<4'` if the distro one is older).
- Full build of dependencies (BDE, NTF) and BlazingMQ: `bin/build-ubuntu.sh` (about 9 minutes on 8 cores; writes to `build/`).
  If `build/blazingmq` already exists, do **not** rerun the full script; rebuild incrementally:
  `cmake --build build/blazingmq --target <target> [--target ...]` (a single test binary plus the broker rebuilds in about 30 seconds).
- Binaries: broker `build/blazingmq/src/applications/bmqbrkr/bmqbrkr.tsk`, tool `build/blazingmq/src/applications/bmqtool/bmqtool.tsk`,
  unit tests `build/blazingmq/tests/<component>.t`.

## Tests

- Unit tests are BDE-style: one binary per component, one case per number. Run `build/blazingmq/tests/mqbblp_routers.t 3` for case 3,
  or loop cases 1..N until the binary returns 255 (case not found). `ctest -R <name>` from `build/blazingmq` also works.
- A failing case prints `Error <file>(<line>): <expression> (failed)`. Quote those lines as evidence; never summarize a test you did not run.
- Python integration tests live in `src/integration-tests` (`./run-tests` there; slow, needs a built broker). Prefer the unit tests
  for root-cause evidence and use the broker scripts below for end-to-end proof.

## Running the broker locally (end-to-end checks)

- `tools/oncall/run-local-broker.sh start|stop` starts a single-node broker on `tcp://localhost:30114` using `docker/single-node/config`.
  Domains available: `bmq.test.mem.priority`, `bmq.test.mem.fanout`, `bmq.test.mem.broadcast`, `bmq.test.persistent.*`.
- `tools/oncall/priority-check.sh` opens a primary consumer (priority 10) and a standby consumer (priority 1) on a priority queue,
  posts messages and reports who received them. Correct behaviour: the primary gets everything, the standby gets nothing.
- `bmqtool` command syntax (stdin): string values must be quoted and `post` payloads are lists, e.g.
  `open uri="bmq://bmq.test.mem.priority/q" flags="read" consumerPriority=10` and `post uri="..." payload=["hello"]`.

## Where things live

- `src/groups/bmq`: client-side and protocol libraries (`bmqa` public API, `bmqp` wire protocol, `bmqt` types).
- `src/groups/mqb`: broker. Queue engines and message routing are in `mqb/mqbblp` (`mqbblp_routers.*` chooses which consumer
  gets each message; `mqbblp_rootqueueengine.*` drives delivery, `mqbblp_queueengineutil.*` helpers). Storage is `mqb/mqbs`, cluster state `mqb/mqbc`.
- Consumer priority: for a given queue (or app in fanout mode) only the consumers at the **highest** priority receive messages;
  lower-priority consumers are standbys and must stay idle until the higher ones go away.

## On-call rules

1. Reproduce before you theorize: find and run the test (or the broker check) that shows the reported behaviour, and quote its output.
2. Root-cause in code: name the file, function and lines, and the commit that introduced the change (`git log -p -- <file>`).
3. Keep the fix minimal and in the code path itself. Add or extend a unit test that would have caught the regression.
4. Prove it: rerun the previously failing cases, run the component's full test binary, and rerun the end-to-end broker check.
5. Open a pull request on a `devin/` branch with a DCO sign-off (`git commit -s`). Describe impact, root cause, fix, and the evidence. Do not merge.
6. Report back in the Slack thread the alert came from: short impact statement, root cause, evidence, PR link, suggested follow-ups.

- Operations console ("BMQ MON", terminal-style UI over the same probe): `tools/oncall/console/server.py` serves http://localhost:8787; `PROBE <GO>` runs tools/oncall/priority-check.sh against the live broker; incident links come from tools/oncall/console/incident.json.
- Trading workstation ("ARGUS", terminal-style UI whose order flow runs on BlazingMQ): `tools/oncall/workstation/server.py` serves http://localhost:8790; it keeps a bmqtool producer and two bmqtool consumers (NY-PRIMARY consumerPriority 10, NJ-DR-STANDBY consumerPriority 1) on an in-memory priority queue; RECON BREAK means the standby executed live orders; `PAGE <GO>` runs tools/oncall/send-alert.py.
