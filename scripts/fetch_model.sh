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
#   scripts/fetch_model.sh --verify      check what is on disk, download nothing
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/config/sglang.env"

revision="${SGLANG_MODEL_REVISION:-}"
force=0
verify_only=0
while (($#)); do
  case "$1" in
    --revision) revision="$2"; shift 2 ;;
    --force)    force=1; shift ;;
    --verify)   verify_only=1; shift ;;
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
  ((verify_only)) && break
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
echo "verifying contents against the Hub's own hashes"
# Sizes are not integrity. The Hub publishes a sha256 for every LFS object and
# a git blob id for every small file at the pinned revision, so every byte that
# the server will load can be checked against what the revision actually is --
# which is the only thing that makes pinning the revision mean anything.
python3 - "$api/revision/$revision?blobs=true" "$dest" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
url, dest = sys.argv[1], pathlib.Path(sys.argv[2])
with urllib.request.urlopen(url, timeout=60) as response:
    siblings = json.load(response).get("siblings", [])
bad = checked = 0
for entry in siblings:
    name = entry["rfilename"]
    if name.startswith("."):
        continue
    path = dest / name
    if not path.is_file():
        print(f"  MISSING   {name}"); bad += 1; continue
    lfs = entry.get("lfs") or {}
    if lfs.get("sha256"):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(16 << 20):
                digest.update(chunk)
        ok, kind = digest.hexdigest() == lfs["sha256"], "sha256"
    elif entry.get("blobId"):
        data = path.read_bytes()
        ok = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() == entry["blobId"]
        kind = "git blob"
    else:
        print(f"  UNHASHED  {name} (the Hub lists no hash for it)"); continue
    checked += 1
    if not ok:
        bad += 1
    print(f"  {'ok      ' if ok else 'MISMATCH'}  {name}  ({kind})")
print(f"{checked} file(s) checked, {bad} problem(s)")
sys.exit(1 if bad else 0)
PY
echo "complete: $dest"
