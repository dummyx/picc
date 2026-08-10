SHELL := /bin/bash

RUN_ID ?= glm52-$(shell date -u +%Y%m%d-%H%M%S)
REPLICATE ?=
REPLICATE_ARG := $(if $(REPLICATE),--replicate $(REPLICATE),)

.PHONY: doctor validate image tests smoke-tests evaluator-smoke setup auth-check pilot main resume visible hidden hidden-all report clean-runs

doctor:
	./scripts/doctor.sh

validate:
	./scripts/validate.sh

image:
	./scripts/build_image.sh

tests:
	./scripts/fetch_tests.sh

smoke-tests:
	./scripts/validate.sh

evaluator-smoke:
	./scripts/smoke_evaluator.sh

setup: doctor validate image tests evaluator-smoke

auth-check:
	python3 scripts/auth_check.py

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

clean-runs:
	@echo "Refusing to delete runs automatically. Remove a specific runs/<id> directory explicitly."
