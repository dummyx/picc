SHELL := /bin/bash

RUN_ID ?= picc-$(shell date -u +%Y%m%d-%H%M%S)
REPLICATE ?=
REPLICATE_ARG := $(if $(REPLICATE),--replicate $(REPLICATE),)

STUDY ?= studies/starter/study.json
CONDITION ?= baseline
PROFILE ?= pilot
REPLICATES ?= 3
PREFIX ?= batch

.PHONY: doctor validate image tests tests-c18 tests-sql tasks-smoke extensions-smoke smoke-tests evaluator-smoke setup auth-check preflight pilot main resume visible hidden hidden-all report \
	study-validate study-list study-schedule study-materialize study-run study-resume study-visible study-hidden study-hidden-all study-report study-summary clean-runs \
	sglang-install sglang-lock model-verify sglang-config inference-smoke sglang-serve sglang-start sglang-stop sglang-status sglang-logs sglang-pin experiment \
	dashboard dashboard-start dashboard-stop dashboard-status

doctor:
	./scripts/doctor.sh

validate:
	./scripts/validate.sh

image:
	./scripts/build_image.sh

tests:
	./scripts/fetch_tests.sh

# Task corpora: chapters 1-18 partitions and the pinned sqllogictest scripts.
tests-c18:
	./scripts/fetch_tests_c18.sh

tests-sql:
	./scripts/fetch_sqllogictest.sh

# Task evaluators in the pinned image with reference-backed and wrong
# candidates (needs Docker and the fetched task corpora).
tasks-smoke:
	./scripts/smoke_tasks.sh

# The two repair extensions in pi/extensions/.
extensions-smoke:
	./scripts/smoke_extensions.sh

smoke-tests:
	./scripts/validate.sh

evaluator-smoke:
	./scripts/smoke_evaluator.sh

setup: doctor validate image tests evaluator-smoke

auth-check:
	python3 scripts/auth_check.py

preflight:
	python3 scripts/preflight_endpoint.py

pilot:
	python3 scripts/run_experiment.py --profile pilot --run-id "$(RUN_ID)" $(REPLICATE_ARG)

main:
	python3 scripts/run_experiment.py --profile main --run-id "$(RUN_ID)" $(REPLICATE_ARG)

resume:
	python3 scripts/run_experiment.py --resume --run-id "$(RUN_ID)"

visible:
	python3 scripts/evaluate_run.py --run-id "$(RUN_ID)" --partition visible

hidden:
	python3 scripts/evaluate_run.py --run-id "$(RUN_ID)" --partition hidden

hidden-all:
	python3 scripts/evaluate_run.py --run-id "$(RUN_ID)" --partition hidden --all-snapshots

report:
	python3 scripts/summarize_run.py --run-id "$(RUN_ID)"

study-validate:
	python3 scripts/study.py validate --study "$(STUDY)"

study-list:
	python3 scripts/study.py list --study "$(STUDY)"

study-schedule:
	python3 scripts/study.py schedule --study "$(STUDY)" --replicates "$(REPLICATES)" --profile "$(PROFILE)"

study-materialize:
	python3 scripts/study.py materialize --study "$(STUDY)" --condition "$(CONDITION)" --run-id "$(RUN_ID)"

study-run:
	python3 scripts/study.py run --study "$(STUDY)" --condition "$(CONDITION)" --profile "$(PROFILE)" --run-id "$(RUN_ID)" $(REPLICATE_ARG)

study-resume:
	python3 scripts/study.py resume --run-id "$(RUN_ID)"

study-visible:
	python3 scripts/study.py evaluate --run-id "$(RUN_ID)" --partition visible

study-hidden:
	python3 scripts/study.py evaluate --run-id "$(RUN_ID)" --partition hidden

study-hidden-all:
	python3 scripts/study.py evaluate --run-id "$(RUN_ID)" --partition hidden --all-snapshots

study-report:
	python3 scripts/study.py report --run-id "$(RUN_ID)"

study-summary:
	python3 scripts/study.py summarize --study "$(STUDY)"

clean-runs:
	@echo "Refusing to delete runs automatically. Remove a specific runs/<id> directory explicitly."

# --- Inference (SGLang) -----------------------------------------------------
# The model server lives in its own virtualenv: the harness's own Python is
# standard library only, and installing a CUDA stack into it would make the
# harness's dependencies unreproducible. Everything the server is launched
# with is pinned in config/sglang.env and recorded per launch under
# runs/inference/. See docs/INFERENCE_SGLANG.md.

sglang-install:
	./scripts/install_sglang.sh

# Record the exact package set of the working venv. Deliberate, not automatic:
# the lock is what install_sglang.sh reproduces, so it should only move when a
# new environment has been measured.
sglang-lock:
	@{ sed -n '/^#/p' config/sglang.lock.txt; PATH="$$HOME/.local/bin:$$PATH" uv pip freeze --python .venv-sglang/bin/python; } > config/sglang.lock.txt.new && mv config/sglang.lock.txt.new config/sglang.lock.txt && echo "locked $$(grep -vc '^#' config/sglang.lock.txt) packages"

# Check every file of the downloaded checkpoint against the Hub's hashes at
# the pinned revision. Downloads nothing.
model-verify:
	./scripts/fetch_model.sh --verify

sglang-config:
	./scripts/sglang_server.sh config

sglang-serve:
	./scripts/sglang_server.sh serve

sglang-start:
	./scripts/sglang_server.sh start

sglang-stop:
	./scripts/sglang_server.sh stop

sglang-status:
	./scripts/sglang_server.sh status

sglang-logs:
	./scripts/sglang_server.sh logs

sglang-pin:
	./scripts/sglang_server.sh pin

# What preflight cannot check: that the endpoint parses tool calls and
# separates reasoning. Both fail silently when the parsers are wrong.
inference-smoke:
	python3 scripts/smoke_inference.py

# --- One-command batch ------------------------------------------------------
# Brings up inference, verifies the endpoint against the frozen config, and
# runs the schedule. PREFIX is the run-id prefix (ids are <PREFIX>-<cond>-r<n>).
#   make experiment STUDY=studies/sql/study.json PREFIX=v16 REPLICATES=3 PROFILE=main
experiment:
	./scripts/start_experiment.sh --study "$(STUDY)" --prefix "$(PREFIX)" \
		--replicates "$(REPLICATES)" --profile "$(PROFILE)"

# --- Results dashboard -------------------------------------------------------
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
