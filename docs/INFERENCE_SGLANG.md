# Inference: SGLang

Record of how the local model is served, and of every serving configuration
this project has run against. The harness freezes its own configuration per
run; this file is the other half, the part that lives outside the harness.

Superseded: the campaign through v15 ran `llama-server` (llama.cpp) against
`unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`. Section 4 records what that was and why
it changed.

## 1. What is installed

SGLang is **not** a dependency of the harness. The harness's Python is standard
library only, deliberately, so that the Python a run executes is the pinned
Docker image and nothing else. SGLang is a dependency of the *operator*: the
process that serves the model the harness talks to over HTTP. It therefore
lives in its own virtualenv, outside the harness import path.

```bash
make sglang-install      # -> scripts/install_sglang.sh -> .venv-sglang/
```

`uv` is used rather than `pip`, for a specific reason: this host's
`/usr/bin/python3.12` ships without `ensurepip`, so `python3 -m venv` produces
an environment with no `pip` in it and `python3 -m ensurepip` fails. `uv` needs
neither, and it is what SGLang's own installation guide recommends.
`--prerelease=allow` is required because SGLang's wheels depend on prerelease
CUDA 13 builds of torch and flashinfer.

Installed and verified 2026-09-21:

| Component | Version |
|---|---|
| sglang | 0.5.20 |
| torch | 2.13.0+cu130 |
| CUDA (torch) | 13.0 |
| uv | 0.12.17 |
| Python | 3.12.3 |
| GPU | NVIDIA GeForce RTX 5090, 32607 MiB |
| Driver | 580.173.02 |
| Compute capability | sm_120 (Blackwell) |

`torch.cuda.get_arch_list()` includes `sm_120`, so the wheels are built for
this card; no source build is needed.

## 2. What is served

### Checkpoint

`RadixArk/Qwen3.8-27B-NVFP4` — the NVFP4 W4A4 body (FP8 attention and GDN
projections, NVFP4 MLPs) with `lm_head` packed to FP4.

Why this variant, on this card:

| Variant | Weights | Fits 32 GB? |
|---|---|---|
| BF16 | ~54 GB | no |
| FP8 (blockwise) | ~28.5 GB | technically, but SGLang records it as "not serviceable beyond bs<=2 on 32GB cards" |
| **NVFP4 W4A4** | **~16.5 GB** | **yes — "recommended for RTX 5090-class GPUs"** |

The RTX 5090 has native FP4 tensor cores, so NVFP4 runs on the fast path rather
than falling back to a weight-only kernel (which is what would happen on an
H200, where SGLang greys the NVFP4 cells out entirely).

There are two RadixArk exports that differ only in the `lm_head`: FP4-packed
and dense BF16. The dense head is ~1.7 GB larger on disk and ~3.2 GB larger at
runtime. The FP4 head is chosen here because the extra headroom goes to the KV
pool, and because on the RTX 5090 every winning launch command is identical
between the two. `nvidia/Qwen3.8-27B-NVFP4` is the same body and the same FP4
head, and is interchangeable.

The checkpoint declares `kv_cache_quant_algo: FP8`, so its own calibration
scales are used for the FP8 KV pool.

### Fetching it

```bash
scripts/fetch_model.sh       # pins the revision, then downloads with resume
```

Not `hf download`: on this host the `hf` CLI hangs with no bytes moving and no
error — process asleep, 4 seconds of CPU over 3 minutes, byte counts frozen —
on both the Xet backend and with `HF_HUB_DISABLE_XET=1`. The same files fetch
over ordinary HTTPS at ~10 MB/s, so `fetch_model.sh` fetches them directly,
with `curl -C -` for resume. This is worth knowing before anyone "fixes" the
script back to the CLI.

The revision is resolved once and written into `config/sglang.env`, and every
file is fetched at that revision, so a later `main` cannot silently change the
checkpoint underneath a campaign. Because `--model-path` is then a local
directory, `--served-model-name` carries the public model id into run metadata.

## 3. Serving configuration

All of it is in `config/sglang.env`, which is the single source of truth.
`scripts/sglang_server.sh` renders it into a YAML config file and launches
`sglang serve --config <file>`.

Launching from a YAML file rather than a command line is deliberate:
`--api-key` has no environment-variable form in SGLang 0.5.20, and a key on the
command line is readable by any user on the host through `ps -eo args`. The
file carrying the key is written mode 0600 into `runs/inference/.runtime/`; the
copy kept in each launch record has the key redacted.

```bash
make sglang-config     # print the resolved configuration (key redacted)
make sglang-start      # launch detached, wait for /health
make sglang-status     # served model, pool sizes, parsers
make sglang-logs
make sglang-stop
```

### The pins, and where they come from

Everything below is SGLang's own measured cell for
`hw=rtx5090 / quant=nvfp4-fp4-head / spec=none / nodes=single`, from their
Qwen3.8-27B cookbook. That cell is measured on v0.5.19 and scored on the full
1319-question GSM8K; all 15 overlay combinations offered for this card served,
at 93.93–94.92%.

| Flag | Value | Why |
|---|---|---|
| `--mem-fraction-static` | `0.9` | the no-speculation operating point for this card |
| `--attention-backend` | `flashinfer` | SM120 requires it; `trtllm_mha` is SM100-only |
| `--kv-cache-dtype` | `fp8_e4m3` | ~2x KV savings using the checkpoint's own scales |
| `--max-running-requests` | `1` | the validated single-stream envelope — and exactly what this harness needs, since it runs one Pi session |
| `--cuda-graph-max-bs-decode` | `1` | pinned together with the above; raise both or neither |
| `--reasoning-parser` | `qwen3` | without it, thinking is not separated from content |
| `--tool-call-parser` | `qwen3_coder` | this template emits `<function=…>` nested in `<tool_call>`; the `hermes` parser reads bare JSON and would silently fail to parse every tool call |
| `--mamba-ssm-dtype` | `bfloat16` | a GDN state slot is 78.4 MB at bf16 against 153.9 MB at fp32, and the difference goes to KV. SGLang measured 97,280 KV tokens at bf16 against 68,588 at fp32 on this card with no speculation |
| `--mamba-radix-cache-strategy` | `extra_buffer_lazy` | 4 state slots per running request instead of 5, at no accuracy cost. On a 32 GB card the state pool, not KV, binds first |
| `--trust-remote-code` | on | required by the checkpoint |

Speculative decoding is **off**. EAGLE/MTP, DSpark and DFlash2 all cost VRAM
that would come out of the KV pool, and this experiment is bound by context
length rather than tokens per second. It is also the only RTX 5090 row that
needs no `--mamba-full-memory-ratio` or `--max-total-tokens` pinning.

### Strict thinking (available, off by default)

`--enable-strict-thinking` builds a reasoner grammar that can force the
end-of-thinking token once a request's thinking budget is spent. The budget is
per request: `custom_params: {"thinking_budget": N}` on a
`/v1/chat/completions` call, which Pi can send through `models.json`
`samplingParams` (`LOCAL_SAMPLING_PARAMS`).

This is the first control this project has had over thinking length that is
not the output cap. Under llama.cpp the only lever was the output cap, and a
reply that reached it while still reasoning produced no text and no tool call
at all — 62% of replies in the strict-typing condition against 3–10%
elsewhere, and raising the cap did not help, because the reasoning expanded to
fill whatever budget it was given (report section 18).

It is off in the committed configuration because turning it on changes what
the model does, which is an experimental decision and not a serving one.

## 4. Configuration log

Every configuration actually launched, in order, with what happened. Add a row
here rather than editing one: the point is the history.

`runs/inference/<timestamp>/` holds the machine-readable version of each
launch — `config.yaml` (redacted), `sglang.env` as it was, `launch.txt` with
versions and GPU, and `server.log`.

| # | Date | Configuration | Outcome |
|---|---|---|---|
| 0 | through 2026-09-20 | **llama.cpp** `llama-server`, `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL` (snapshot `4ca72078`), n_ctx 131072, port 4545, sampling `temperature=1.0 top_p=0.95 top_k=20 min_p=0` | Ran batches v10–v15. Two harness defects found and fixed (compaction overflow, truncation compounding). Left unexplained: the strict-typing condition produced nothing, with 62% of replies cut off mid-reasoning; raising the output cap from 32768 to 65536 did not help. Retired in favour of SGLang. |

<!-- Append new rows below. -->

## 5. Harness-side settings that must agree

The server and the harness are configured separately and must not drift apart.
`make preflight` checks the ones that can be checked:

| Harness (`.env` / `config/defaults.env`) | Server (`config/sglang.env`) |
|---|---|
| `MODEL_ID` | `SGLANG_SERVED_MODEL_NAME` — must be equal |
| `LOCAL_BASE_URL` | `SGLANG_HOST` / `SGLANG_PORT` |
| `LOCAL_CONTEXT_WINDOW` | must fit in the server's usable context — see below |
| `LOCAL_MAX_OUTPUT` | bounded by `pi/settings.json` compaction budget |

The context check is the one that is new with SGLang. SGLang sizes its KV pool
from whatever VRAM is left after the weights, so it will happily start with a
pool far smaller than the `--context-length` it advertises, and a conversation
that outgrows the pool is rejected mid-run. `preflight_endpoint.py` reads both
`context_length` and `max_total_num_tokens` from `/get_server_info` and refuses
to start when `LOCAL_CONTEXT_WINDOW` exceeds the smaller of the two.
