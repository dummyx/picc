SHELL := /bin/bash

# Settings for the targets below; override on the command line, e.g.
#   make study-run STUDY=studies/sql/study.json CONDITION=python PROFILE=main RUN_ID=v18-sql-python-r1 REPLICATE=1
STUDY ?= studies/c10/starter/study.json
CONDITION ?= baseline
PROFILE ?= pilot
REPLICATES ?= 3
PREFIX ?= batch
RUN_ID ?= picc-$(shell date -u +%Y%m%d-%H%M%S)
REPLICATE ?=
REPLICATE_ARG := $(if $(REPLICATE),--replicate $(REPLICATE),)

.PHONY: setup doctor image tests tests-c18 tests-sql \
	validate evaluator-smoke tasks-smoke extensions-smoke \
	sglang-install sglang-lock model-verify sglang-config sglang-serve sglang-start sglang-stop sglang-status sglang-logs sglang-pin \
	preflight inference-smoke auth-check \
	experiment \
	study-validate study-list study-schedule study-materialize study-run study-resume study-visible study-hidden study-hidden-all study-report study-summary \
	dashboard dashboard-start dashboard-stop dashboard-status \
	clean-runs

# --- Setting up a machine -----------------------------------------------------
# Prerequisites, checks, the pinned image, the three tasks' test sets, and the
# scorer smoke test. The model server is set up separately (below).

setup: doctor validate image tests tests-c18 tests-sql evaluator-smoke

doctor:
	./scripts/checks/doctor.sh

image:
	./docker/build.sh

# Test sets, each fetched at a pinned revision and split into the part the
# agent may see and the hidden part it is scored on.
tests:        # C compiler, chapters 1-10 -> data/partitions
	./scripts/test_sets/fetch_tests.sh

tests-c18:    # C compiler, chapters 1-18 -> data/partitions-c18 (checked against studies/c18/selection.json)
	./scripts/test_sets/fetch_tests_c18.sh

tests-sql:    # SQL engine -> data/partitions-sql (checked against studies/sql/selection-record.json)
	./scripts/test_sets/fetch_sqllogictest.sh

# --- Checks ---------------------------------------------------------------------

validate:           # no Docker needed: syntax, unit tests, deterministic splits
	./scripts/checks/validate.sh

evaluator-smoke:    # chapters 1-10 scorer and fuzz oracle in the pinned image
	./scripts/checks/smoke_evaluator.sh

tasks-smoke:        # chapters 1-18 and SQL scorers in the pinned image
	./scripts/checks/smoke_tasks.sh

extensions-smoke:   # the two repair extensions in pi/extensions/, in the pinned image
	./scripts/checks/smoke_extensions.sh

# --- Model server (SGLang) ------------------------------------------------------
# The server lives in its own virtualenv: the harness's own Python is
# standard library only, and installing a CUDA stack into it would make the
# harness's dependencies unreproducible. Everything the server is launched
# with is pinned in config/sglang.env and recorded per launch under
# runs/inference/. See docs/INFERENCE_SGLANG.md.

sglang-install:
	./scripts/model_server/install_sglang.sh

# Record the exact package set of the working venv. Deliberate, not automatic:
# the lock is what install_sglang.sh reproduces, so it should only move when a
# new environment has been measured.
sglang-lock:
	@{ sed -n '/^#/p' config/sglang.lock.txt; PATH="$$HOME/.local/bin:$$PATH" uv pip freeze --python .venv-sglang/bin/python; } > config/sglang.lock.txt.new && mv config/sglang.lock.txt.new config/sglang.lock.txt && echo "locked $$(grep -vc '^#' config/sglang.lock.txt) packages"

# Check every file of the downloaded checkpoint against the Hub's hashes at
# the pinned revision. Downloads nothing. (Downloading is
# scripts/model_server/fetch_model.sh without --verify.)
model-verify:
	./scripts/model_server/fetch_model.sh --verify

sglang-config:      # the resolved launch configuration, key redacted
	./scripts/model_server/sglang_server.sh config

sglang-serve:       # run in the foreground
	./scripts/model_server/sglang_server.sh serve

sglang-start:       # run in the background and wait until ready
	./scripts/model_server/sglang_server.sh start

sglang-stop:
	./scripts/model_server/sglang_server.sh stop

sglang-status:      # health, served model, memory pool sizes
	./scripts/model_server/sglang_server.sh status

sglang-logs:
	./scripts/model_server/sglang_server.sh logs

sglang-pin:         # pin SGLANG_MODEL_REVISION in config/sglang.env
	./scripts/model_server/sglang_server.sh pin

# The served model and usable context must match what the harness freezes.
preflight:
	python3 scripts/model_server/preflight_endpoint.py

# What preflight cannot check: that the endpoint parses tool calls and
# separates reasoning, and that a thinking budget is enforced. These fail
# silently when the server is misconfigured.
inference-smoke:
	python3 scripts/model_server/smoke_inference.py

# One minimal request through Pi in the pinned image.
auth-check:
	python3 scripts/model_server/auth_check.py

# --- Running a batch ----------------------------------------------------------
# Brings up the model server, verifies it against the frozen configuration,
# and runs every scheduled run with its hidden scoring and report, unattended.
# Run ids are <PREFIX>-<condition>-r<n>.
#   make experiment STUDY=studies/sql/study.json PREFIX=v18 REPLICATES=3 PROFILE=main
experiment:
	./scripts/start_experiment.sh --study "$(STUDY)" --prefix "$(PREFIX)" \
		--replicates "$(REPLICATES)" --profile "$(PROFILE)"

# --- One study step at a time -------------------------------------------------
# What `make experiment` does, as separate steps. Every run is made from a
# study file (studies/<task>/.../study.json); see studies/README.md.

study-validate:     # check a manifest and list its conditions
	python3 scripts/study.py validate --study "$(STUDY)"

study-list:
	python3 scripts/study.py list --study "$(STUDY)"

study-schedule:     # a fixed, shuffled run order for REPLICATES repetitions
	python3 scripts/study.py schedule --study "$(STUDY)" --replicates "$(REPLICATES)" --profile "$(PROFILE)"

study-materialize:  # build a condition's frozen copy without running the agent
	python3 scripts/study.py materialize --study "$(STUDY)" --condition "$(CONDITION)" --run-id "$(RUN_ID)"

study-run:          # one run of one condition
	python3 scripts/study.py run --study "$(STUDY)" --condition "$(CONDITION)" --profile "$(PROFILE)" --run-id "$(RUN_ID)" $(REPLICATE_ARG)

study-resume:       # continue a run that stopped early (marks it not comparable)
	python3 scripts/study.py resume --run-id "$(RUN_ID)"

study-visible:      # score the last saved version on the visible tests
	python3 scripts/study.py evaluate --run-id "$(RUN_ID)" --partition visible

study-hidden:       # score the last saved version on the hidden tests
	python3 scripts/study.py evaluate --run-id "$(RUN_ID)" --partition hidden

study-hidden-all:   # score every saved version on the hidden tests
	python3 scripts/study.py evaluate --run-id "$(RUN_ID)" --partition hidden --all-snapshots

study-report:       # runs/<id>/report.md and report.json
	python3 scripts/study.py report --run-id "$(RUN_ID)"

study-summary:      # every eligible run of a study -> runs/study-results/<study-id>/
	python3 scripts/study.py summarize --study "$(STUDY)"

# --- Results dashboard ----------------------------------------------------------
# A read-only web page over runs/ and the write-ups: batches, runs, the agent's
# conversation, the files it wrote, test results, comparisons and reports.
# It listens on this machine only (http://localhost:$(DASHBOARD_PORT)); from
# another computer, forward the port over SSH. The SGLang venv's Python is used
# when present because counting reasoning tokens needs its `tokenizers`
# package; everything else is standard library. See docs/DASHBOARD.md.
DASHBOARD_PORT ?= 8765
DASHBOARD_PYTHON := $(if $(wildcard .venv-sglang/bin/python),.venv-sglang/bin/python,python3)

dashboard:
	$(DASHBOARD_PYTHON) analysis/dashboard/server.py --port "$(DASHBOARD_PORT)"

dashboard-start:
	$(DASHBOARD_PYTHON) analysis/dashboard/server.py --port "$(DASHBOARD_PORT)" --background

dashboard-stop:
	python3 analysis/dashboard/server.py --stop

dashboard-status:
	python3 analysis/dashboard/server.py --status

clean-runs:
	@echo "Refusing to delete runs automatically. Remove a specific runs/<id> directory explicitly."
