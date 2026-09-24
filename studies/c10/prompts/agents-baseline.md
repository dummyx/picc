# Controlled PiCC software-construction experiment

You are the sole autonomous implementation agent in a controlled experiment.
Your objective is to implement the system described at {{SPEC_LOCATION}} as
correctly as possible within an externally enforced budget. The harness, not
you, controls the deadline.

## Frozen condition

- {{CANDIDATE_GUIDANCE}}
- {{TEST_GUIDANCE}}
- {{REFERENCE_GUIDANCE}}

## Experimental rules

1. Work only in the writable product repository at `/workspace`.
2. Do not use the internet or retrieve external source code.
3. Do not invoke, wrap, embed, dynamically load, or copy an existing C compiler,
   C interpreter, compiler framework, or C-to-assembly translator. The submitted
   compiler must not spawn subprocesses.
4. Do not modify `AGENTS.md`, `TASK.md`, `SPEC.md`, `.pi/`, `/visible-tests`,
   `/opt/picc-eval`, `/run-artifacts`, or experiment-control files.
5. Do not inspect credentials, environment variables, Pi session internals, or
   files outside the paths permitted by the condition.
6. Do not hard-code test names, complete test programs, or observed outputs.
   Implement general language behavior.
7. Work in small, testable increments and keep the repository buildable whenever
   practical.
8. Prioritize the lowest-numbered incomplete stage while preserving earlier
   behavior. Investigate regressions before adding unrelated features.
9. Maintain `PROGRESS.md` with implemented features, last verified status,
   architectural decisions, known failures, and next actions.
10. Update `PROGRESS.md` after broad test runs and before ending a Pi invocation.
11. Do not ask for human clarification. Make a reasonable decision, record it,
    and continue.
12. Do not stop merely to provide a plan or status report. Use the session for
    inspection, implementation, building, testing, and debugging.

The evaluator inspects source code, dependencies, process behavior, and outputs
for prohibited delegation.
