# Controlled PiCC software-construction experiment

You are the sole autonomous implementation agent in a controlled experiment.
Your objective is to implement the system in `TASK.md` as correctly as possible
within an externally enforced budget. The harness, not you, controls the final
deadline.

## Experimental rules

1. Work only in the writable product repository at `/workspace`.
2. Do not use the internet or retrieve external source code.
3. Do not invoke, wrap, embed, dynamically load, or copy an existing C compiler,
   C interpreter, compiler framework, or C-to-assembly translator to implement
   PiCC. The submitted PiCC process must not spawn subprocesses.
4. Do not modify `AGENTS.md`, `TASK.md`, `.pi/`, `/visible-tests`,
   `/opt/picc-eval`, `/run-artifacts`, or experiment-control files.
5. Do not inspect environment variables, credentials, Pi session internals, or
   files outside the permitted workspace and visible-test corpus.
6. Do not hard-code test names, complete visible test programs, or expected
   outputs. Implement general language behavior.
7. Use the `test_visible` tool for behavioral feedback. Do not invoke GCC,
   Clang, TinyCC, or another C compiler directly.
8. Work in small, testable increments and keep the repository buildable whenever
   practical.
9. Prioritize the lowest-numbered stage that is not substantially passing, while
   preserving all earlier stages.
10. Investigate regressions before adding unrelated features.
11. Maintain `PROGRESS.md` with concise, operational state:
    - implemented features;
    - last verified test status;
    - important architectural invariants and decisions;
    - known failures;
    - next concrete actions.
12. Update `PROGRESS.md` after broad test runs and before ending a Pi invocation.
13. Do not ask for human clarification. Make a reasonable decision, record it,
    and continue.
14. Do not stop merely to provide a plan or progress report. Spend the available
    session inspecting, implementing, building, testing, and debugging.

The evaluator will inspect source code, dependencies, process behavior, and
outputs for prohibited delegation to an existing compiler.
