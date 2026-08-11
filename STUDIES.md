# Controlled factor studies

PiCC's original single-run workflow remains the baseline reproduction harness.
The additive study layer under [`studies/`](studies/README.md) materializes
immutable one-factor conditions for prompts, specifications, test access and
feedback, implementation language/framework/scaffold, and reference access.

Start with:

```bash
make study-validate
make study-list
make study-schedule REPLICATES=3 PROFILE=main
make study-run CONDITION=baseline PROFILE=pilot RUN_ID=baseline-pilot-r1 REPLICATE=1
```

See [`docs/STUDY_PROTOCOL.md`](docs/STUDY_PROTOCOL.md) before running the main
matrix.
