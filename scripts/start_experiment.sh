#!/usr/bin/env bash
# Bring up inference and run a study batch, from one command.
#
# Until now the two halves were separate: an operator started the model server
# by hand, outside the repository, and then ran the make targets. Nothing tied
# the two together, so a batch could be started against a server running a
# different checkpoint, a different context length, or no server at all — and
# the failure showed up as dead rounds hours later. This script is the single
# entry point: it starts the pinned server if it is not already healthy, waits
# for it, refuses to continue unless preflight verifies the endpoint against
# the frozen configuration, and only then runs the schedule.
#
#   scripts/start_experiment.sh --study studies/sql/study.json --prefix v16 \
#       --replicates 3 --profile main
#
#   scripts/start_experiment.sh --study studies/sql/study.json --prefix probe \
#       --condition python --profile pilot --single
#
# Options:
#   --study PATH        study manifest (required)
#   --prefix NAME       run-id prefix; ids are <prefix>-<condition>-r<n>
#   --replicates N      replicates per condition (default 3)
#   --profile NAME      pilot | main (default main)
#   --condition NAME    with --single, the one condition to run
#   --single            run one condition once instead of a schedule
#   --replicate N       with --single, the replicate number (default 1). Use a
#                       distinct number for a control run: a summary treats two
#                       runs of the same condition and replicate as a duplicate
#                       cell and refuses the whole study.
#   --no-server         assume a server is already running; do not start one
#   --stop-after        stop the server when the batch finishes
#   --dry-run           print what would run, start nothing
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

study=""; prefix=""; replicates=3; profile=main; condition=""; replicate=1
single=0; no_server=0; stop_after=0; dry_run=0

while (($#)); do
  case "$1" in
    --study)       study="$2"; shift 2 ;;
    --prefix)      prefix="$2"; shift 2 ;;
    --replicates)  replicates="$2"; shift 2 ;;
    --profile)     profile="$2"; shift 2 ;;
    --condition)   condition="$2"; shift 2 ;;
    --replicate)   replicate="$2"; shift 2 ;;
    --single)      single=1; shift ;;
    --no-server)   no_server=1; shift ;;
    --stop-after)  stop_after=1; shift ;;
    --dry-run)     dry_run=1; shift ;;
    -h|--help)     sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }
say() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }

[[ -n "$study" ]]  || die "--study is required"
[[ -f "$study" ]]  || die "no study manifest at $study"
[[ -n "$prefix" ]] || die "--prefix is required (run ids are built from it)"
if ((single)) && [[ -z "$condition" ]]; then die "--single needs --condition"; fi

server="$ROOT/scripts/sglang_server.sh"

if ((dry_run)); then
  say "server configuration:"
  "$server" config | sed 's/^/    /'
  if ((single)); then
    say "would run one $condition at profile=$profile as $prefix-$condition-r$replicate"
  else
    say "would schedule $replicates replicate(s) per condition from $study at profile=$profile,"
    say "then chain them with run ids $prefix-<condition>-r<n>"
  fi
  exit 0
fi

# 1. Inference. An already-healthy server is left alone: restarting one
#    mid-campaign would change the serving configuration under runs that are
#    meant to be comparable.
if ((no_server)); then
  say "skipping server startup (--no-server)"
elif "$server" status >/dev/null 2>&1; then
  say "server already healthy, leaving it alone"
else
  say "starting SGLang"
  "$server" start 1800 || die "server did not become ready"
fi

# 2. Verify what is actually being served against what the harness froze.
say "preflight"
(cd "$ROOT" && make preflight) || die "preflight failed; not starting the batch"

# 3. Run.
finish() {
  if ((stop_after)); then say "stopping server"; "$server" stop || true; fi
}
trap finish EXIT

if ((single)); then
  run_id="$prefix-$condition-r$replicate"
  say "single run $run_id (replicate $replicate)"
  (cd "$ROOT" && make study-run STUDY="$study" CONDITION="$condition" \
      PROFILE="$profile" RUN_ID="$run_id" REPLICATE="$replicate")
  (cd "$ROOT" && make study-hidden-all RUN_ID="$run_id")
  (cd "$ROOT" && make study-report RUN_ID="$run_id")
else
  schedule="$ROOT/runs/$prefix-schedule.json"
  mkdir -p "$ROOT/runs"
  say "scheduling $replicates replicate(s) per condition into ${schedule#"$ROOT"/}"
  (cd "$ROOT" && python3 scripts/study.py schedule --study "$study" \
      --replicates "$replicates" --profile "$profile" --output "$schedule" >/dev/null)
  say "running chain; progress in runs/$prefix-chain.log"
  "$ROOT/scripts/chain_study.sh" "$schedule" "$prefix"
fi

say "batch finished"
