#!/usr/bin/env bash
# Run a study schedule sequentially and unattended: for every scheduled slot
# not yet completed, verify the endpoint (make preflight), run the condition,
# evaluate every snapshot on the hidden partition, and write the per-run
# report. Slots whose run directory already holds a report are skipped, so
# the chain can be restarted after an interruption.
#
#   scripts/chain_study.sh <schedule.json> <run-id-prefix>
#
# The schedule comes from `make study-schedule ... --output` (or
# `python3 scripts/study.py schedule --output`); run ids become
# <prefix>-<condition>-r<replicate>. Progress goes to runs/<prefix>-chain.log.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
schedule="$1"
prefix="$2"
log="$ROOT/runs/$prefix-chain.log"

say() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$log"; }

mapfile -t slots < <(python3 - "$schedule" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
for row in payload["rows"]:
    print(f"{row['sequence']}\t{row['replicate']}\t{row['condition']}")
PY
)
study="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["study_id"])' "$schedule")"
study_path="$(python3 - "$schedule" <<'PY'
import json, sys
row = json.load(open(sys.argv[1]))["rows"][0]
print(row["command"].split("STUDY=")[1].split()[0])
PY
)"
profile="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["profile"])' "$schedule")"

say "chain start: study=$study profile=$profile slots=${#slots[@]}"
for slot in "${slots[@]}"; do
  IFS=$'\t' read -r sequence replicate condition <<<"$slot"
  run_id="$prefix-$condition-r$replicate"
  if [[ -f "$ROOT/runs/$run_id/report.md" ]]; then
    say "slot $sequence $run_id: already reported, skipping"
    continue
  fi
  say "slot $sequence $run_id: preflight"
  if ! (cd "$ROOT" && make preflight >>"$log" 2>&1); then
    say "slot $sequence $run_id: preflight FAILED, chain aborted"
    exit 1
  fi
  if [[ ! -d "$ROOT/runs/$run_id" ]]; then
    say "slot $sequence $run_id: run"
    (cd "$ROOT" && make study-run STUDY="$study_path" CONDITION="$condition" PROFILE="$profile" RUN_ID="$run_id" REPLICATE="$replicate" >>"$log" 2>&1)
    say "slot $sequence $run_id: run exit $?"
  else
    say "slot $sequence $run_id: run directory exists, evaluating only"
  fi
  say "slot $sequence $run_id: hidden-all"
  (cd "$ROOT" && make study-hidden-all RUN_ID="$run_id" >>"$log" 2>&1)
  say "slot $sequence $run_id: hidden-all exit $?"
  (cd "$ROOT" && make study-report RUN_ID="$run_id" >>"$log" 2>&1)
  say "slot $sequence $run_id: report exit $?"
done
(cd "$ROOT" && make study-summary STUDY="$study_path" >>"$log" 2>&1)
say "chain done: summary exit $?"
