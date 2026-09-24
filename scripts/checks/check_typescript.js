#!/usr/bin/env node
// Syntax-check the agent extensions: the two repair extensions in
// pi/extensions/ and the templates in studies/runtime/ that scripts/study.py
// renders into every run. A template's __PLACEHOLDER__ tokens are replaced by
// JSON values when it is rendered; `null` stands in for them here.
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

const root = path.resolve(__dirname, "..", "..");
const sources = [
  ...fs.readdirSync(path.join(root, "pi", "extensions")).filter((n) => n.endsWith(".ts")).map((n) => path.join("pi", "extensions", n)),
  ...fs.readdirSync(path.join(root, "studies", "runtime")).filter((n) => n.endsWith(".ts.in")).map((n) => path.join("studies", "runtime", n)),
].sort();

let failed = false;
for (const relative of sources) {
  const filename = path.join(root, relative);
  const source = fs.readFileSync(filename, "utf8").replace(/__[A-Z0-9_]+__/g, "null");
  const result = ts.transpileModule(source, {
    fileName: filename.replace(/\.in$/, ""),
    reportDiagnostics: true,
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
      strict: true,
    },
  });
  const diagnostics = result.diagnostics || [];
  if (diagnostics.length > 0) {
    failed = true;
    console.error(`${relative}:`);
    for (const diagnostic of diagnostics) {
      console.error(`  ${ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n")}`);
    }
  } else {
    console.log(`${relative}: syntax OK`);
  }
}
process.exit(failed ? 1 : 0);
