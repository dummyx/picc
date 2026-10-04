# Documents

Start with the [front page](../README.md). For the results, read the
[latest report](REPORT_2026-10-05.md) (the v18 and v19 batches) and the
[full write-up of every batch](../analysis/report.md). To browse runs,
conversations and files, use the [results dashboard](DASHBOARD.md).

## Every batch

A batch is a set of runs started together to answer one question. From v3
on, each batch's plan was written and committed before its first run, and
changes made during a batch are recorded in the plan as amendments. Times are UTC. "Runs" counts
the full-length runs, with shorter trial runs in brackets.

| Batch | When | Task | What was compared | Runs | What it found | Read |
|---|---|---|---|---|---|---|
| early | Aug 18–23 | C compiler, ch. 1–10 | trial runs of the first variants | 1 (+14) | setting up; not analysed | — |
| v2 | Aug 24–25 | C compiler, ch. 1–10 | four ways of writing the prompt and specification | (15) | no difference bigger than the normal run-to-run spread | [write-up §1–6](../analysis/report.md) |
| v3 | Sep 2 | C compiler, ch. 1–10 | tests withheld from the agent | 6 | looked like an effect; later traced to agents hanging on their own commands | [plan](EXPERIMENT_PLAN.md), §7 |
| v4 | Sep 6–7 | C compiler, ch. 1–10 | TypeScript with strict type checks vs plain JavaScript | 6 | no difference | [plan](EXPERIMENT_PLAN_v4.md), §8 |
| v5 | Sep 10 | C compiler, ch. 1–10 | tests withheld, with improved scoring | 8 | the v3 effect did not repeat | [plan](EXPERIMENT_PLAN_v5.md), [results](../analysis/v5-results.md), §10 |
| v6 | Sep 11 | C compiler, ch. 1–10 | tests withheld, with a 2-minute limit on each shell command | 8 | no difference; runs became far more consistent | [plan](EXPERIMENT_PLAN_v6.md), [results](../analysis/v6-results.md), §12, [report](REPORT_2026-09-12.md) |
| v7 | Sep 11–12 | C compiler, ch. 1–10 | TypeScript strict vs JavaScript again, on the fixed setup | 8 | no difference; typed code about 40% larger | [plan](EXPERIMENT_PLAN_v7.md), [results](../analysis/v7-results.md), §13, [report](REPORT_2026-09-12.md) |
| v8 | Sep 12–13 | C compiler, ch. 1–10 | test results sent to the agent every 10 minutes | 8 | no difference in correctness; changed how the agent worked | [plan](EXPERIMENT_PLAN_v8.md), [results](../analysis/v8-results.md), §14, [report](REPORT_2026-09-13.md) |
| v9 | Sep 13–14 | C compiler, ch. 1–10 | a 143-word specification, crossed with tests withheld | 12 | the short specification did as well; without tests two of three agents replaced the real assembler with their own simulator | [plan](EXPERIMENT_PLAN_v9.md), [results](../analysis/v9-results.md), §15, [report](REPORT_2026-09-14.md) |
| v10 | Sep 16–18 | C compiler, ch. 1–18, and SQL engine | Rust, Python, and Python with strict type checks | 18 (+2) | both new tasks leave room to improve (best 0.501 and 0.795); strict typing looked costly on SQL, mixed up with setup problems | [plan](EXPERIMENT_PLAN_v10.md), §16, [report](REPORT_2026-09-18.md) |
| v11 | Sep 18 | SQL engine, plus one trial run of the C compiler, ch. 1–18 | v10 repeated after four fixes | 5 (+2) | stopped: agents' conversations kept breaking | [plan](EXPERIMENT_PLAN_v11.md), §17 |
| v12 | Sep 18 | SQL engine | v10 repeated after an output-limit fix | 4 | stopped for the same reason | [plan](EXPERIMENT_PLAN_v12.md), §17 |
| probes | Sep 19 | SQL engine | short runs testing thinking settings | (5) | the thinking level was not the cause | §17.5 |
| v13 | Sep 19 | SQL engine | how often each variant finishes a working engine | 3 | stopped: the conversation summaries still failed | [plan](EXPERIMENT_PLAN_v13.md), §17.7 |
| v14 | Sep 19 | SQL engine | v13 restarted after a summary fix | 2 | stopped: the fix was not enough | [plan](EXPERIMENT_PLAN_v14.md), §17.7 |
| v15 | Sep 20–21 | SQL engine | Rust, Python, and Python with strict type checks | 10 | the setup held (no broken conversations); typed Python produced nothing, so typing stayed unanswered | [plan](EXPERIMENT_PLAN_v15.md), §18 |
| v16 | Sep 21 | SQL engine | typed Python with and without a cap on the model's thinking | 2 (+1) | both built working engines (0.814 and 0.785); the cap removes wasted rounds and was kept | [plan and results](EXPERIMENT_PLAN_v16.md), §19 |
| v17 | Sep 21–22 | SQL engine | five languages: Rust, Python, typed Python, JavaScript, TypeScript | 15 | nothing broke; the spread within each language is bigger than the differences between languages | [plan](EXPERIMENT_PLAN_v17.md), [results](../analysis/v17-results.md), §20, [report](REPORT_2026-09-23.md) |
| v18 | Oct 2–3 | SQL engine | Rust, Python, typed Python | 6 (stopped) | three of six zeroed by output-contract mistakes the agent could not see; stopped and redesigned as v19 | [plan](EXPERIMENT_PLAN_v18.md), §21 |
| v19 | Oct 3–4 | SQL engine, ch. 1-18 compiler | Rust, Python, typed Python, + one minimal-specification Rust run | 19 | the example fixed the output contract; two new zeros (a crate in a subdirectory, `mypy` never run); typing −0.008 / +0.060, no effect; minimal spec −0.222 (one reading) | [plan](EXPERIMENT_PLAN_v19.md), §22, [report](REPORT_2026-10-05.md) |
| v20 | Oct 4– | SQL engine, ch. 1-18 compiler | as v19, 21 runs, every round message carries the harness's build-and-example check | running | — | [plan](EXPERIMENT_PLAN_v20.md) |

"§" numbers are sections of [analysis/report.md](../analysis/report.md).
v16 and v17 are summarised in §19 and §20 and written up in full in their
plan and report. The study files
behind each batch, and why their ids change from batch to batch, are listed
in [studies/README.md](../studies/README.md).

## How things work (kept up to date)

- [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md): the fixed rules of one
  run: rounds, time limits, when a run stops, how it is scored, what the
  agent can and cannot do, and when a stopped run may be continued.
- [STUDY_PROTOCOL.md](STUDY_PROTOCOL.md): how the variants of a study are
  set up, run, excluded and compared, and how a batch is re-scored after a
  correction.
- [DATA_DICTIONARY.md](DATA_DICTIONARY.md) and
  [STUDY_DATA_DICTIONARY.md](STUDY_DATA_DICTIONARY.md): every file a run
  leaves under `runs/<run-id>/` and every field in it.
- [INFERENCE_SGLANG.md](INFERENCE_SGLANG.md): the model server, how it is
  set up, and a log of every server configuration that has been used.
- [DASHBOARD.md](DASHBOARD.md): the results dashboard.

## Records (written at the time, not updated since)

Records written before 2026-09-24 name files by their locations at the time.
On that day `studies/` was organized into one folder per task; every move is
listed in [studies/moved.json](../studies/moved.json) (for example
`studies/sql/study.json` stayed where it was, while `studies/starter/study.json`
is now `studies/c10/starter/study.json`).

- **Plans**, one per batch: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md) (v3),
  then `EXPERIMENT_PLAN_v4.md` to `EXPERIMENT_PLAN_v20.md`.
- **Reports to the project owner**:
  [2026-09-12](REPORT_2026-09-12.md) (v6, v7 and the hanging commands),
  [2026-09-13](REPORT_2026-09-13.md) (v8),
  [2026-09-14](REPORT_2026-09-14.md) (v9),
  [2026-09-18](REPORT_2026-09-18.md) (v10),
  [2026-09-23](REPORT_2026-09-23.md) (v17),
  [2026-10-05](REPORT_2026-10-05.md) (v18 stopped, v19, the v20 design).
- [SLIDES_2026-09-13.md](SLIDES_2026-09-13.md) and
  [MEETING_NOTE_2026-09-14.md](MEETING_NOTE_2026-09-14.md): a talk and a
  meeting note on the chapters 1–10 campaign.
- [RELEASE_STATUS.md](RELEASE_STATUS.md): what had been checked when the
  first version of the harness was packaged, on 2026-08-10.
