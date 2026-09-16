SHELL := /bin/bash

RUN_ID ?= picc-$(shell date -u +%Y%m%d-%H%M%S)
REPLICATE ?=
REPLICATE_ARG := $(if $(REPLICATE),--replicate $(REPLICATE),)

STUDY ?= studies/starter/study.json
CONDITION ?= baseline
PROFILE ?= pilot
REPLICATES ?= 3

.PHONY: doctor validate image tests tests-c18 tests-sql tasks-smoke smoke-tests evaluator-smoke setup auth-check preflight pilot main resume visible hidden hidden-all report \
	study-validate study-list study-schedule study-materialize study-run study-resume study-visible study-hidden study-hidden-all study-report study-summary clean-runs

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
