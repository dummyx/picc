#!/usr/bin/env bash
# Evaluator-only deliberately wrong candidate: accepts every program and emits
# the same assembly (main returning 0) regardless of the input.
set -u
cat > "$3" <<'ASM'
	.globl main
main:
	movl $0, %eax
	ret
	.section .note.GNU-stack,"",@progbits
ASM
exit 0
