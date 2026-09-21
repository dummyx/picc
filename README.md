# PiCC: Pi coding-agent compiler-construction starter pack

This repository starts a small, controlled reproduction of the long-horizon
"coding agent builds a compiler" experiment.

A single **Pi Coding Agent** session, backed by an **operator-declared model**,
starts from an empty product repository and implements **PiCC**: a Rust compiler
for the core language features covered by Chapters 1–10 of the *Writing a C
Compiler* test suite.

The base workflow is intentionally narrow and remains the runnable feasibility
study. An additive controlled-study layer covers prespecified prompt,
specification, test-access, implementation-substrate, and reference-access
conditions; see [`STUDIES.md`](STUDIES.md).

## Results so far

Eight planned in advance batches (71 main runs) varied prompts, specifications,
test access, test feedback, and static typing one factor at a time, then
crossed specification detail with test access. None detectably changed the
compiler's behavioral correctness on the corpus oracle; each changed how the
agent worked. The one candidate effect with a mechanism (v9: without tests,
two of three agents replaced the assembler with a self-written simulator) is
awaiting replication. The campaign summary, per-batch sections, and the harness
defects found along the way are in [`analysis/report.md`](analysis/report.md);
experiment plans are under `docs/EXPERIMENT_PLAN*.md`; session reports for
the project owner under `docs/REPORT_*.md`.

## Frozen default configuration

| Item | Default |
|---|---|
| Starter pack | `0.1.0` |
| Pi | `@earendil-works/pi-coding-agent@0.85.1` |
| Provider | Operator-declared in `MODEL_PROVIDER`; recorded per run |
| Model | Operator-declared in `MODEL_ID`; recorded per run |
| Thinking setting | `max` |
| Agent topology | One persistent Pi session |
| Bash default timeout | `@cad0p/pi-bash-timeout@0.1.0`: 120 s when the agent sets none |
| Implementation | Rust `1.88.0`, standard library only |
| Product interface | `target/release/picc INPUT.c -o OUTPUT.s` |
| Target assembly | GNU-compatible x86-64 System V assembly |
| Test source revision | `ae12014d2dec14488f3f80d14df4b6d8e4634d7d` |
| Split | 70% visible / 30% hidden, grouped by test family |
| Pilot | 2 hours, at most 6 Pi invocations, Stages 1–6 |
| Main | 12 hours, at most 30 Pi invocations, Stages 1–10 |
| Container platform | `linux/amd64` |

The harness assumes no model. `MODEL_PROVIDER` and `MODEL_ID` have no defaults
and must be declared in `.env` before any run; an empty value is an error rather
than a guess. Both are frozen for the run and recorded in `metadata.json`. When
the declared provider is a hosted plan, the model ID and client configuration
are frozen, but the exact server-side checkpoint cannot be pinned.

## What is included

- a pinned Pi, Rust, and TypeScript Docker image;
- hosted Coding Plan authentication through `ZAI_API_KEY` or
  `ZAI_CODING_CN_API_KEY`, or a local OpenAI-compatible endpoint;
- fixed `AGENTS.md`, task, initial, and continuation prompts;
- a deterministic visible/hidden test split;
- an evaluator-side GCC behavioral oracle;
- automatic Git snapshots after every Pi invocation;
- Pi JSON event and session logging;
- post-hoc hidden evaluation for the final or every snapshot;
- report generation;
- an optional, materialized controlled-study layer under
  [`studies/`](studies/README.md);
- two small, inspectable Pi extensions:
  - `experiment-tools.ts` adds `test_visible` and `experiment_status`;
  - `experiment-guard.ts` blocks obvious policy violations and logs attempts.

No third-party Pi packages or skills are installed. This keeps the harness
surface small and avoids introducing another evolving dependency into the first
experiment.

The checks completed before packaging, and the checks that must run on the
experiment host, are recorded in [`docs/RELEASE_STATUS.md`](docs/RELEASE_STATUS.md).

## Quick start

Requirements:

- Docker with Linux container support;
- Git;
- Python 3.11 or later;
- GNU Make;
- credentials for the declared provider, such as an active Z.AI Coding Plan and
  API key, **or** a local OpenAI-compatible endpoint (see
  [Using a local model](#using-a-local-model)).

On Apple Silicon, Docker runs the pinned `linux/amd64` image under emulation so
that generated x86-64 assembly can be linked and executed. This is slower but
keeps the target architecture identical across hosts.

### 1. Declare the model and configure access

```bash
cp .env.example .env
$EDITOR .env
```

Every run needs an explicit `MODEL_PROVIDER` and `MODEL_ID`; neither has a
default. The supported providers are `zai`, `zai-coding-cn`, and `local`.

For the global Z.AI Coding Plan endpoint:

```dotenv
MODEL_PROVIDER=zai
MODEL_ID=the_model_you_declare
ZAI_API_KEY=your_key_here
```

For the Z.AI China endpoint:

```dotenv
MODEL_PROVIDER=zai-coding-cn
MODEL_ID=the_model_you_declare
ZAI_CODING_CN_API_KEY=your_key_here
```

For a self-hosted endpoint, see [Using a local model](#using-a-local-model).

Do not commit `.env`. Prefer a dedicated experiment key with the smallest
practical quota and scope.

### 2. Build and prepare the test split

```bash
make setup
```

This performs local validation, builds the pinned image, checks the evaluator
with a tiny mock compiler, downloads the pinned upstream test revision, and
creates `data/partitions/visible` and `data/partitions/hidden`.

The source revision is fixed in `config/defaults.env`. The first setup does not
track the moving upstream default branch.

### 3. Verify provider access

```bash
make auth-check
```

This loads the two project-local extensions and sends one minimal request through
Pi using the declared `MODEL_PROVIDER` and `MODEL_ID`. Against a hosted plan it
consumes a small amount of plan quota; with `MODEL_PROVIDER=local` it exercises
the local endpoint instead.

### 4. Run a non-reportable pilot

```bash
make pilot RUN_ID=picc-pilot-01
```

The pilot is for infrastructure and feasibility calibration. Do not include it
as one of the main independent repetitions.

If the pilot stops with `round_timeout` or `pi_process_failure`, it can be
continued before any post-hoc evaluation or report is generated:

```bash
make resume RUN_ID=picc-pilot-01
```

Resume is an audited recovery operation, not a new independent run. It uses the
frozen profile and configuration, continues the same Pi session at the next
unused round, and deducts the active time and Pi invocations already consumed.
A resumed trajectory is marked noncomparable with the uninterrupted fixed
protocol and must not be included as a main independent repetition.

Inspect:

```bash
make hidden RUN_ID=picc-pilot-01
make report RUN_ID=picc-pilot-01
less runs/picc-pilot-01/report.md
```

### 5. Run the main repetitions

Use at least three independent run IDs:

```bash
make main RUN_ID=picc-r1 REPLICATE=1
make main RUN_ID=picc-r2 REPLICATE=2
make main RUN_ID=picc-r3 REPLICATE=3
```

The harness does not pin a sampling seed, and Pi exposes no deterministic seed
for the supported providers. These are independent stochastic repetitions, not
seeded deterministic reruns.

## Using a local model

Setting `MODEL_PROVIDER=local` replaces the hosted Coding Plan with any
OpenAI-compatible endpoint (llama.cpp `llama-server`, LM Studio, vLLM, Ollama).
The harness then generates a Pi `models.json` describing exactly one provider
and one model from the `LOCAL_*` configuration, freezes it into
`runs/<run-id>/control/pi/models.json`, and records the endpoint shape in
`metadata.json`. Resume revalidates all of it like every other frozen setting.

This project serves its own model with SGLang. That side is set up once and
then driven from the repository:

```bash
make sglang-install          # SGLang into its own virtualenv (not the harness's)
scripts/fetch_model.sh       # pin the checkpoint revision and download it
make sglang-start            # launch, wait for /health
make sglang-status           # served model, KV pool size, parsers
```

Every pin lives in `config/sglang.env`, every launch is recorded under
`runs/inference/<timestamp>/`, and the whole arrangement — which checkpoint,
which flags, and why each one — is written up in
[docs/INFERENCE_SGLANG.md](docs/INFERENCE_SGLANG.md).

Then select it in `.env` (no hosted key is required):

```dotenv
MODEL_PROVIDER=local
MODEL_ID=RadixArk/Qwen3.8-27B-NVFP4     # = SGLANG_SERVED_MODEL_NAME
MODEL_THINKING=high
LOCAL_BASE_URL=http://127.0.0.1:30000/v1
LOCAL_NETWORK_MODE=host
LOCAL_CONTEXT_WINDOW=131072
```

and verify the endpoint end to end before any run:

```bash
make preflight      # served model and usable context match the frozen config
make auth-check     # one real Pi request through the pinned image
```

Or do all of it in one command, which is the intended way to start a batch:

```bash
make experiment STUDY=studies/sql/study.json PREFIX=v16 REPLICATES=3 PROFILE=main
```

That starts the server if it is not already healthy, refuses to continue
unless preflight verifies the endpoint against the frozen configuration, and
only then runs the schedule.

Any other OpenAI-compatible endpoint (llama.cpp `llama-server`, LM Studio,
vLLM, Ollama) still works: set the `LOCAL_*` values to match it and skip the
`sglang-*` targets. `make preflight` understands both `llama-server` and
SGLang metadata.

Notes:

- `MODEL_ID` must name the served model; the harness refuses an empty value so
  runs cannot be mislabeled. Single-model servers usually ignore the requested
  ID, so the configured value is also the run's provenance label — keep it
  exact.
- Keep `LOCAL_CONTEXT_WINDOW` within the server's real usable context; Pi uses
  it for compaction thresholds. With SGLang this is not just the
  `--context-length` flag: the KV pool is sized from whatever VRAM is left
  after the weights, so the pool can be much smaller than the advertised
  context and a conversation that outgrows it is rejected mid-run.
  `make preflight` reads both numbers from `/get_server_info` and refuses to
  start when the window exceeds the smaller one. `LOCAL_MAX_OUTPUT` caps
  output tokens per request.
- Docker Desktop (macOS/Windows) resolves `host.docker.internal` even for a
  server bound to `127.0.0.1`. On a Linux engine the harness adds
  `host.docker.internal:host-gateway`, but the server must listen on an
  interface reachable from the Docker bridge (for example `--host 0.0.0.0`,
  ideally with `--api-key` plus a matching `LOCAL_API_KEY` in `.env`).
- `LOCAL_THINKING_FORMAT=qwen-chat-template` (the default) drives
  `chat_template_kwargs.enable_thinking` for local Qwen-style thinking models;
  set `LOCAL_REASONING=0` for non-thinking models, and use
  `LOCAL_SAMPLING_PARAMS` (a JSON object; for Qwen3.8 thinking mode the
  published recommendation is
  `{"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0}`) to pin
  sampling server-side. Everything lands in the frozen `models.json`.
- Provenance: the harness freezes the client configuration. The server side is
  frozen separately, by `config/sglang.env` (copied into every materialization)
  and by the per-launch records under `runs/inference/`.
- Runs against a local model are a different experimental condition. Do not
  pool them with hosted-provider repetitions.

Evaluate the final hidden snapshot and produce a report:

```bash
for id in picc-r1 picc-r2 picc-r3; do
  make hidden RUN_ID="$id"
  make report RUN_ID="$id"
done
```

To obtain a hidden-score trajectory for every saved round:

```bash
make hidden-all RUN_ID=picc-r1
make report RUN_ID=picc-r1
```

## Experiment behavior

Each run uses one persistent Pi session. A **round** is one non-interactive Pi
invocation. After Pi returns, the outer harness:

1. commits all product changes to a harness-controlled Git history;
2. evaluates the frozen snapshot on the visible partition;
3. records the score in harness state;
4. resumes the same Pi session with the identical continuation prompt.

The run ends at the first applicable limit: wall-clock budget, maximum rounds,
per-round timeout, Pi/provider failure, or full visible completion followed by
one review round. There is no human steering during a run.

### Audited resume

`make resume RUN_ID=...` is available only for a completed run whose termination
reason is `round_timeout` or `pi_process_failure`. It does not retry the failed
round: every attempted Pi invocation consumes one round, and the next invocation
uses the next sequential round number with Pi's `--continue` mode. Elapsed time
is cumulative active harness time across execution attempts; time between the
original attempt and resume is not charged, and consumed time is never restored.

Before resuming, the harness verifies the frozen model and non-secret
configuration, immutable Docker image ID, sequential round and snapshot ledgers,
unused next-round artifact paths,
one valid Pi session, and a clean workspace whose Git HEAD matches the latest
snapshot. It also refuses exhausted budgets, active or locked runs, and runs
that have already been postprocessed by `make visible`, `make hidden`,
`make hidden-all`, or `make report`.

Each resume is recorded in `metadata.json` and `artifacts/resume-events.jsonl`.
The metadata sets `protocol_comparable` to false because restarting the harness
is an operator intervention under the fixed protocol. A resumed run remains the
same stochastic trajectory and cannot be counted as another repetition.

Pi can call `test_visible` during a round. That tool returns compact per-stage
scores and representative failures while writing the complete result outside
model-visible context. Hidden tests are never mounted into the agent container.

## Test scope

The default starter uses the **standalone core** of Chapters 1–10. The split
script excludes:

- extra-credit features;
- multi-file `libraries` cases;
- helper C libraries;
- assembly helper libraries;
- tests requiring the math library.

This simplifies the first experiment to one C input file and one assembly
output file per case. It still exercises lexing, parsing, semantic validation,
expressions, variables, control flow, functions, and single-file storage-class
behavior.

A later extension can add multi-file compilation, object emission, and linking.
Do not silently change the default test scope between repetitions.

### Scoring

For each stage, the evaluator computes separate pass rates for valid and invalid
programs, then averages the available classes. The primary score is the mean of
the stage scores. This prevents a compiler that rejects every input from earning
a misleadingly high score from invalid tests.

The report also includes the ordinary test-level micro-average.

For valid programs, the evaluator:

1. compiles and runs the test with evaluator-side GCC to obtain behavior;
2. asks PiCC to emit assembly;
3. assembles and links that output with evaluator-side GCC;
4. compares exit status, standard output, and standard error.

For invalid programs, PiCC must terminate normally with a nonzero status and
must not leave a nonempty assembly output.

## Pi extensions

### `experiment-tools.ts`

This extension adds:

- `test_visible`: controlled test execution with concise model feedback;
- `experiment_status`: current round, remaining budget, and last visible score;
- compaction and provider-error audit events.

Pi's own `--mode json` stream remains the canonical detailed trajectory. The
extension does not replace or rewrite Pi's default compaction policy.

### `experiment-guard.ts`

This extension blocks obvious attempts to:

- download source or packages;
- call GCC, Clang, TinyCC, or similar compilers directly;
- inspect environment credentials or harness-owned artifacts;
- modify task, test, Pi configuration, or Git-control files;
- write outside `/workspace`.

Pi's bash tool has no default timeout, and its maintainer declined to add one
(earendil-works/pi#2987). An agent that runs a program its own half-built
compiler miscompiled into an infinite loop therefore blocks the session for the
rest of the round: across the v3–v5 batches 18 of 20 runs lost a median 34
minutes to one such call, while 99% of completed commands finished within 5 s.
The image pins the community package `@cad0p/pi-bash-timeout` (loaded through
`pi/settings.json`), which re-registers the bash tool with a 120 s default
timeout when the agent sets none; an explicit timeout always wins, and Pi
kills the command's process group when it fires. The guard logs each cut-off
as `bash_timeout_fired` in `guard.jsonl`, and the run report counts them.

It is an **audit and accident-prevention layer, not a security boundary**.
Extensions and shell tools execute with the Pi process's container permissions.
The provider credential is necessarily available to the Pi process. A
deliberately adversarial agent could potentially obfuscate a forbidden action.
For stronger isolation, move tool execution to a separate sandbox service or use
a dedicated microVM/container sandbox such as Gondolin, while keeping model calls
in a credential-bearing controller.

## Output layout

A run produces:

```text
runs/<run-id>/
├── metadata.json
├── report.json
├── report.md
├── workspace.git.bundle
├── workspace/                  # final product repository and Git history
├── control/                    # frozen prompts, settings, extensions, and
│                               # models.json for local-endpoint runs
└── artifacts/
    ├── events/                 # Pi JSON event stream and stderr per round
    ├── sessions/               # canonical Pi session JSONL
    ├── evaluations/            # full visible/hidden test results
    ├── tool-evaluations/       # test_visible results
    ├── rounds.jsonl
    ├── snapshots.jsonl
    ├── resume-events.jsonl
    ├── hidden-scores.jsonl
    ├── extension-events.jsonl
    ├── guard.jsonl
    ├── reference-cache/
    └── state.json
```

See [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) for field-level notes.

## Recommended protocol discipline

Before main runs:

1. finish the pilot;
2. fix infrastructure defects only;
3. freeze this repository commit, Docker image ID, prompts, split manifests, and
   configuration;
4. write the experiment plan fields in `docs/EXPERIMENT_PLAN.md`;
5. do not inspect hidden results until the run is complete.

During main runs:

- do not send extra messages to Pi;
- do not edit the workspace;
- do not treat a resumed trajectory as an uninterrupted main repetition;
- record provider outages or quota exhaustion as run outcomes;
- only exclude runs using pre-declared infrastructure-failure rules.

## Important validity limitations

1. **Public-corpus contamination.** The upstream compiler tests and related book
   material may be represented in model training data. Report this explicitly
   and add newly generated private holdout tests before making strong capability
   claims.
2. **Hosted-model drift.** A hosted model is provider-managed. The starter
   records the declared model ID, client configuration, and timestamps but
   cannot archive the server checkpoint.
3. **No deterministic seed.** Repetitions measure stochastic run variability;
   they are not bitwise reproductions.
4. **Guard limitations.** The default single-container setup is practical, not
   high-assurance adversarial containment. Candidate processes also share an
   evaluator namespace with the selected test partition.
5. **One target.** Results support a claim about this PiCC task and harness, not
   arbitrary large-scale software construction.
6. **Provider quotas.** Provider throttling or quota exhaustion can terminate a
   run. Pi/provider errors are logged and must not be hidden by manual steering.

## Useful commands

```bash
make doctor                 # local prerequisites
make validate               # syntax and deterministic-split checks
make image                  # build pinned experiment image (base pinned by digest)
make preflight              # check the local endpoint and its model alias
make tests                  # fetch pinned corpus and partition it
make evaluator-smoke        # verify Stage-1 evaluator path
make auth-check             # minimal request via the configured provider
make pilot RUN_ID=...
make main RUN_ID=... REPLICATE=1
make resume RUN_ID=...      # audited continuation after timeout/process failure
make visible RUN_ID=...     # reevaluate final snapshot on visible tests
make hidden RUN_ID=...      # final hidden snapshot
make hidden-all RUN_ID=...  # all saved snapshots
make report RUN_ID=...
make study-validate          # validate the controlled-study definition
make study-schedule          # deterministic randomized-block run order
```

Configuration overrides belong in `.env`, but any override used in a reported
run must be preserved and disclosed. Non-secret effective configuration is
copied into `metadata.json`. The pre-rename `ZAI_PROVIDER`/`ZAI_MODEL`/
`ZAI_THINKING` keys are refused with a migration error rather than ignored;
only the `ZAI_API_KEY` and `ZAI_CODING_CN_API_KEY` credential names remain.

## Upstream references

- Pi Coding Agent: <https://github.com/earendil-works/pi>
- Pi JSON event mode: <https://github.com/earendil-works/pi/blob/v0.85.1/packages/coding-agent/docs/json.md>
- Pi extension API: <https://github.com/earendil-works/pi/blob/v0.85.1/packages/coding-agent/docs/extensions.md>
- Compiler test corpus: <https://github.com/nlsandler/writing-a-c-compiler-tests>

Provider-specific, relevant only when the declared provider is `zai` or
`zai-coding-cn`:

- Z.AI Pi Coding Agent guide: <https://docs.z.ai/devpack/tool/pi>
- Z.AI model-switching guide: <https://docs.z.ai/devpack/latest-model>

The starter-pack harness code is MIT-licensed. The downloaded upstream test
corpus retains its own license, copied to `data/UPSTREAM_TEST_LICENSE` by
`make tests`.
