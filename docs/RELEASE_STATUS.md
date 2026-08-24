# Starter-pack release status

Prepared on 2026-08-10.

## Validated in the build environment

- Python scripts compile under Python 3.13.
- Shell scripts pass `bash -n`.
- `pi/settings.json` parses as JSON.
- Both project-local Pi extensions transpile successfully as TypeScript.
- The smoke-corpus split is deterministic for the frozen seed.
- Visible and hidden test IDs are disjoint.
- Test-family groups do not cross the visible/hidden boundary.
- Manifest SHA-256 values match copied test files.
- The evaluator was functionally exercised on the Stage-1 smoke partition with
  a mock PiCC build path; it produced a 1.0 macro and micro score.

## Requires validation on the experiment host

This environment did not provide a Docker daemon or credentials for a model
provider. Consequently, the following are intentionally performed by `make setup`
and `make auth-check` on the experiment host:

- building the `linux/amd64` Docker image;
- installing the pinned Pi npm package inside that image;
- downloading the exact upstream test revision;
- running the Dockerized evaluator smoke test;
- loading the extensions with the pinned Pi runtime and sending a live minimal
  request to the declared `MODEL_PROVIDER`/`MODEL_ID`;
- executing an end-to-end Pi trajectory.

Do not start reportable runs until `make setup` and `make auth-check` both pass.
Record the resulting Docker image ID and manifest hashes in the pre-registration.
