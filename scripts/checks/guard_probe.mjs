// Drives the rule checker (studies/runtime/experiment-guard.ts.in, rendered
// with the SQL task's plain-Python rules) against shell commands.
// Run by scripts/checks/smoke_extensions.sh inside the pinned image.
import assert from "node:assert/strict";
import { bashBlockReason, commandSkeleton } from "./experiment-guard.ts";

const allowed = (command) => assert.equal(bashBlockReason(command), undefined, command);
const blocked = (command, reason) => {
  const actual = bashBlockReason(command);
  assert.ok(actual && actual.includes(reason), `${JSON.stringify(command)} -> ${actual}`);
};

// The four commands blocked by mistake in the v17 batch (the text that set the
// rule off, in the command shape the agent used). Each is code being written
// or run by another program, not a command the shell runs.
allowed(`cd /workspace && python3 - <<'EOF'
import re
src = open('pisql.py').read()
src = re.sub(r"(-> )(list|dict|set|tuple)\\b(?!\\[)", lambda m: m.group(1), src)
open('pisql.py', 'w').write(src)
EOF`);
allowed(`cd /workspace && python3 -c "
import re
src = open('pisql.py').read()
src = re.sub(r'(-> )(list|dict|set|tuple)\\b(?!\\[)', rep, src)
"`);
allowed(`cd /workspace && python3 - <<'PYEOF'
new='''/// SQLite's real output form: %.15g plus a decimal point or exponent.
    // %.15g leaves no decimal point; SQLite adds ".0"
'''
PYEOF`);
allowed(`cat >> /workspace/src/pisql.ts << 'EOF'
    if (cc >= 0xd800 && cc <= 0xdbff) { i += 1; }
EOF`);

// Other data that reads like a command.
allowed(`grep -nE "list|set|tuple" pisql.py | head`);
allowed(`echo "done; set" && git commit -qm "parser; cc of tokens"`);
allowed(`cargo build --release 2>&1 | tail -5 # then curl the result; set`);
allowed(`cat > notes.txt <<EOF
next: rm AGENTS.md is not allowed; env
EOF
ls`);
allowed(`echo $((1 << 4))
ls`);
allowed(`set -e; cd /workspace && python3 pisql.py t.sql`);

// The same words as commands are still blocked, wherever the command starts.
blocked(`sqlite3 :memory: "select 1"`, "existing database engine");
blocked(`cd /workspace && echo "select 1;" | sqlite3`, "existing database engine");
blocked(`cd /workspace\nsqlite3 t.db`, "existing database engine");
blocked(`cd /workspace && \\\n  sqlite3 t.db`, "existing database engine");
blocked(`cat > t.sql <<EOF\nselect 1;\nEOF\nsqlite3 < t.sql`, "existing database engine");
blocked(`env`, "environment inspection");
blocked(`cd /workspace; set | grep KEY`, "environment inspection");
blocked(`curl -s example.org`, "network/download");
blocked(`gcc -o t t.c`, "C/C++ compiler");
blocked(`echo x; cc t.c`, "C/C++ compiler");
blocked(`rm -f /workspace/AGENTS.md`, "experiment-control");
blocked(`echo $((1 << 4))\nsqlite3 t.db`, "existing database engine");

// Text handed to a shell is commands, not data.
blocked(`bash -c "cd /tmp && sqlite3 t.db"`, "existing database engine");
blocked(`bash -c 'sqlite3 t.db'`, "existing database engine");
blocked(`bash <<EOF\nsqlite3 t.db\nEOF`, "existing database engine");
blocked(`cat <<EOF | sh\ncurl -s example.org\nEOF`, "network/download");
blocked(`find . -name '*.sql' | xargs -I{} sh -c 'sqlite3 x.db < {}'`, "existing database engine");

// Rules about text anywhere still read everything, pasted code included.
blocked(`python3 - <<'EOF'\nimport sqlite3\nEOF`, "delegating to an existing database engine");
blocked(`python3 -c "import urllib.request"`, "programmatic network access");
blocked(`cat > a.py <<'EOF'\nopen('/run-artifacts/state.json')\nEOF`, "harness-internal");
blocked(`pip install sqlglot`, "dependency download");

// What the rules about commands get to read.
assert.equal(commandSkeleton(`a "x; y" && b 'p|q' # c; d\ne`), `a "" && b '';e`);
assert.equal(commandSkeleton(`cat <<'EOF' > f\nbody; set\nEOF\nls`), `cat << > f;ls`);
assert.equal(commandSkeleton(`sh -c 'a; b' 2>&1`), `sh -c;a; b;2>&1`);

console.log("guard: ok");
