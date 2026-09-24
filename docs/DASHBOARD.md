# Results dashboard

A web page for looking at the experiment's results: every batch, every run, the
agent's whole conversation, the files it wrote, the test results, side-by-side
comparisons, and the write-ups in `docs/` and `analysis/`. It only reads; it
never changes anything under `runs/` or in the repository.

## Starting it

```bash
make dashboard-start     # starts in the background, prints the address
make dashboard-status    # is it running?
make dashboard-stop      # stops it
make dashboard           # or: run it in this terminal (Ctrl-C stops it)
```

Then open <http://localhost:8765>. `DASHBOARD_PORT=9000 make dashboard-start`
uses another port.

It listens on this machine only. From another computer, forward the port over
SSH and open the same address there:

```bash
ssh -N -L 8765:127.0.0.1:8765 <user>@<this machine>
```

It can listen on the network instead (`--host` on
`analysis/dashboard/server.py`), but then anyone who can reach the machine
could read the runs' records, so it asks for an access code, printed at
start-up. Do this only on purpose.

The first start reads every run once (about half a minute for 167 runs) and
keeps what it read in `~/.cache/picc-dashboard/`; later starts are immediate. A
run whose files change, such as one that is running, is re-read automatically.

## What is on it

- **Batches**: one card per batch with every run's final score, and a
  "Running now" section while a batch is going.
- **A batch**: scores by variant, progress over time, a table of every run
  (scores, time, replies, tokens, tool calls, failures, blocked commands,
  conversation summaries, code size), the score on each hidden test, where the
  time went, tokens written and read, tool calls, and what each agent left
  behind. Trial runs and runs that did not finish are listed separately.
- **A run**, in six tabs:
  - *Overview*: scores after each round, a minute-by-minute picture of what
    the agent was doing (model writing, tools running, summarizing, work lost
    at the round's end), how big the conversation was at each reply, tokens
    written per reply, and a table of rounds.
  - *Conversation*: every prompt, reply (with its thinking), tool call and
    result, and every conversation summary, round by round, with search.
    Clicking a point on any chart opens that moment here.
  - *Files it wrote*: every saved version of the workspace, file by file,
    with the changes each round made.
  - *Test results*: every hidden and visible test for each saved version,
    with what went wrong and the build output.
  - *Tool use and behaviour*: calls by tool, why calls failed, what the shell
    commands did, the slowest commands, commands the rule checker refused,
    conversation summaries, replies that did not call a tool, thinking per
    reply.
  - *Setup*: the variant, the model and server settings, the budget, the
    agent's settings and everything it was given.
- **Compare runs**: any runs side by side, over time and number by number.
- **Reports**: the Markdown write-ups, rendered.
- **Model server**: whether the inference server is up and every recorded
  launch configuration (secret settings hidden).

## Where the numbers come from

The same records, measured the same way, as `analysis/v17_internals.py` and
`docs/REPORT_2026-09-23.md`; for the 15 v17 runs every total matches that
report. Scores re-computed after a batch (`analysis/v<N>-rescore/`,
`analysis/v6-rescore.json`) replace the values recorded during the run and are
marked with `*`.

Thinking tokens are not in the run records (they are recorded as 0), so they
are counted from the streamed reasoning with the model's own tokenizer. That
needs the SGLang virtualenv's Python, which `make dashboard` uses when it is
there; without it the page says they were not counted rather than guessing.

A tool call's time is the time from the reply being saved to its result being
saved. Commands cut off by the 120-second limit measure 120.1 seconds this way,
which is how the method was checked.

The code is in `analysis/dashboard/` (`picc_data.py` reads the records,
`server.py` serves them, `static/` is the page); `tests/test_dashboard.py`
checks it against a small made-up run whose timings are known exactly.
