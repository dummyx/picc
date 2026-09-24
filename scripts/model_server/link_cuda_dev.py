#!/usr/bin/env python3
"""Give the pip-installed CUDA toolkit the layout a linker expects.

SGLang JIT-compiles some kernels on first launch and links them with
`-L$CUDA_HOME/lib64 -lcudart`, which is how a system CUDA install is laid out.
The pip packages are laid out differently: libraries live in `lib/`, not
`lib64/`, and only versioned sonames are shipped (`libcudart.so.13`), because
the unversioned development symlinks belong to a `-dev` package that has no
pip equivalent. The result is a server that compiles its kernels successfully
and then fails to link them.

This adds the missing links inside the virtualenv. It is idempotent and
touches nothing outside the venv passed to it.
"""

from __future__ import annotations

import sys
from pathlib import Path


def link_tree(root: Path) -> int:
    """Add lib64 -> lib and unversioned .so links under one nvidia/cu* dir."""
    lib = root / "lib"
    if not lib.is_dir():
        return 0
    created = 0
    lib64 = root / "lib64"
    if not lib64.exists():
        lib64.symlink_to("lib")
        created += 1
    for versioned in sorted(lib.glob("lib*.so.*")):
        plain = lib / (versioned.name.split(".so.")[0] + ".so")
        if not plain.exists():
            plain.symlink_to(versioned.name)
            created += 1
    return created


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: link_cuda_dev.py <venv>", file=sys.stderr)
        return 2
    venv = Path(sys.argv[1]).resolve()
    roots = sorted(venv.glob("lib/python*/site-packages/nvidia/cu*"))
    if not roots:
        print("no pip CUDA packages found; nothing to link")
        return 0
    total = sum(link_tree(root) for root in roots)
    print(f"cuda dev links: {total} created across {len(roots)} package(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
