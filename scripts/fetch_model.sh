#!/usr/bin/env bash
# Download the pinned model checkpoint for the local SGLang server.
#
# This does not use the `hf` CLI: on this host it hangs with no bytes moving
# and no error, on both the Xet and the plain HTTP backend, while the same
# files fetch at full speed over ordinary HTTPS. So the files are fetched
# directly, with resume, into a plain directory that --model-path points at.
#
# A plain directory is also what makes the checkpoint pinnable. The repository
# revision is resolved once, recorded in config/sglang.env, and every file is
# fetched at that revision, so a later `main` cannot silently change what the
# experiment runs against. --served-model-name keeps the model's public id in
# run metadata even though the path on disk is local.
#
#   scripts/fetch_model.sh [--revision SHA] [--force]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/config/sglang.env"

revision="${SGLANG_MODEL_REVISION:-}"
force=0
while (($#)); do
  case "$1" in
    --revision) revision="$2"; shift 2 ;;
    --force)    force=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

repo="$SGLANG_MODEL_REPO"
dest="${SGLANG_MODEL_DIR:-$HOME/models/${repo##*/}}"
api="https://huggingface.co/api/models/$repo"

# Size of a remote file. LFS objects report their real size in x-linked-size;
# content-length on those is the size of the redirect body, not the file.
remote_size() {
  curl -fsSLI "$1" | tr -d '\r' \
    | awk 'BEGIN{IGNORECASE=1} /^x-linked-size:/{x=$2} /^content-length:/{c=$2} END{print (x!="" ? x : c)}'
}

if [[ -z "$revision" ]]; then
  revision="$(curl -fsSL "$api" | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha"])')"
  [[ -n "$revision" ]] || { echo "could not resolve a revision for $repo" >&2; exit 1; }
  python3 - "$ROOT/config/sglang.env" "$revision" <<'PY'
import pathlib, re, sys
path, rev = pathlib.Path(sys.argv[1]), sys.argv[2]
path.write_text(re.sub(r"^SGLANG_MODEL_REVISION=.*$", f"SGLANG_MODEL_REVISION={rev}",
                       path.read_text(), flags=re.M))
PY
  echo "pinned SGLANG_MODEL_REVISION=$revision"
fi

mkdir -p "$dest"
echo "repo      $repo"
echo "revision  $revision"
echo "into      $dest"
echo

mapfile -t files < <(curl -fsSL "$api/revision/$revision" | python3 -c '
import json, sys
for f in json.load(sys.stdin).get("siblings", []):
    name = f["rfilename"]
    if not name.startswith("."):
        print(name)
')
(( ${#files[@]} )) || { echo "no files listed for $repo@$revision" >&2; exit 1; }

for name in "${files[@]}"; do
  out="$dest/$name"
  mkdir -p "$(dirname "$out")"
  url="https://huggingface.co/$repo/resolve/$revision/$name"
  want="$(remote_size "$url")"
  if [[ -f "$out" && "$force" == "0" && -n "$want" && "$(stat -c %s "$out")" == "$want" ]]; then
    printf '  have  %-40s %12s bytes\n' "$name" "$want"
    continue
  fi
  printf '  get   %-40s %12s bytes\n' "$name" "${want:-?}"
  curl -fSL --retry 8 --retry-delay 5 --retry-all-errors -C - -o "$out" "$url"
done

echo
echo "verifying sizes"
fail=0
for name in "${files[@]}"; do
  url="https://huggingface.co/$repo/resolve/$revision/$name"
  want="$(remote_size "$url")"
  got="$(stat -c %s "$dest/$name" 2>/dev/null || echo 0)"
  if [[ -n "$want" && "$got" != "$want" ]]; then
    echo "  MISMATCH $name: have $got, expected $want" >&2
    fail=1
  fi
done
(( fail )) && { echo "download incomplete" >&2; exit 1; }
echo "complete: $dest"
