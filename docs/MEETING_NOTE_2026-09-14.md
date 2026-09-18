# Meeting note, 2026-09-14: PiCC

## What the project is

A coding agent, driven by a local 27B model, builds a C compiler from an
empty folder in 90 minutes. We change one thing about its working conditions
at a time and measure whether the compiler comes out more or less correct.

Correctness is measured two ways, both hidden from the agent: 104 test
programs from the book's test suite, and 1000 random C programs whose
output is compared with GCC. Both give a score from 0 to 1. With three or
four runs per condition, a difference smaller than about 0.13 cannot be
told from noise.

## Results so far (seven rounds, 59 runs)

| Round | What we changed | Effect on correctness | Effect on how the agent works |
|---|---|---|---|
| v2 | prompt style, spec detail (4 variants) | none | detailed specs cost 50 to 90% more tokens |
| v3, v5, v6 | tests taken away | none (v3 showed −0.14, later traced to a bug in our setup) | agent writes 50 to 170 tests of its own, 100 more turns |
| v4, v7 | TypeScript with strict types vs plain JavaScript | none (+0.004) | 40% more code, ten times more self-tests, type checker run 20+ times |
| v8 | test results pushed to the agent every 10 min | none (−0.025) | agent asks for tests half as often, writes ten times more of its own |

In short: nothing we changed made the compiler better or worse. Everything
we changed altered the agent's behavior.

## Insights

- The agent compensates for whatever it lacks. No tests: it writes them.
  Typed language: it leans on the type checker. It arrives at the same
  compiler by a different route.
- It never fetches anything from the internet (blocked, and never
  attempted in 5155 shell commands). It writes its own tests because it
  already knows what a C program should return.
- The biggest source of variation was our own setup, not the conditions.
  Example: a shell command could hang for 45 minutes; that alone produced a
  false "tests hurt" result. Six such bugs found and fixed, all caught by
  writing the analysis plan down before running.
- Scores stop moving once the model can finish the task. Behavior keeps
  moving. Behavior is the thing to measure.

## Caveat

The task comes from a public book with a public test suite. The model has
very likely seen both. So the results say: for a task the model already
knows, the working conditions do not matter. They do not say specifications
and tests never matter.

## Finished today: does the agent need a specification or tests at all?

Four conditions: full specification or a minimal one (143 words: the
command line, what to output, ten one-line feature names, no book
reference), each with or without tests. Three runs per condition, twelve
runs, 01:35 to 19:42 JST. Two scoring bugs found during the run were fixed
afterwards and every run re-scored; nine of twelve came back identical, the
two affected runs got their real scores.

| Condition | Hidden tests (median) | GCC agreement (median) | Code lines | Own tests |
|---|---:|---:|---:|---:|
| full spec, with tests | 0.97 | 1.00 | 2159 | 10 |
| minimal spec, with tests | 0.90 | 0.98 | 3529 | 0 |
| full spec, no tests | 0.87 | 0.80 | 2100 | 0 |
| minimal spec, no tests | 0.88 | 0.996 | 3918 | 13 |

Time and tokens: the same everywhere (89 to 90 minutes, about 285k tokens).

What it shows:

- **The specification does not matter for this task.** A 143-word spec
  gives the same agreement with GCC as the full one. The model already
  knows C. The only thing the full spec adds is which malformed programs
  the test suite wants rejected, worth about 0.05 on the hidden tests.
- **The minimal spec makes the compiler 60 to 80 percent bigger**, because
  the agent adds pointers, shifts, and types nobody asked for.
- **Tests matter in one specific way.** Without tests, two of the three
  full-spec agents never used the real assembler. Each wrote its own
  simulator of the machine and tested against that. Their compilers pass
  their own tests and emit assembly the real assembler rejects (GCC
  agreement 0.80 and 0.20). The agent can be its own oracle for C, which it
  knows, but not for assembler syntax, which it has to check. Every
  minimal-spec agent did check, because its spec said nothing about the
  target. This is the first effect of tests we have seen with a mechanism
  behind it. Three runs is not enough to call it; it needs a replication.
- The task is confirmed as one the model recalls. Specifications can only
  be studied on a task the model cannot recall.

## Proposed next steps

1. Replicate the tests effect: a no-tests round with more runs, recording
   whether each agent uses the real assembler. About one day.
2. A task the model cannot recall: keep the C compiler but change the
   language rules (operator precedence, evaluation order, array indexing).
   Scoring still works because the changed language can be translated back
   to normal C. Fallback: chapters 11 to 20 of the book.

## Questions

1. Replicate the tests effect first, or go straight to the new task?
2. Anything to add or cut in the group talk?
