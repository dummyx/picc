#!/usr/bin/env bash
# Evaluator-only deliberately wrong candidate: rejects every program with a diagnostic.
echo "error: rejected by the reject-all candidate" >&2
exit 1
