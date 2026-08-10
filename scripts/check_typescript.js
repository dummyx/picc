#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const directory = path.join(root, "pi", "extensions");
let failed = false;
for (const name of fs.readdirSync(directory).filter((name) => name.endsWith(".ts")).sort()) {
  const filename = path.join(directory, name);
  const source = fs.readFileSync(filename, "utf8");
  const result = ts.transpileModule(source, {
    fileName: filename,
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
    console.error(`${name}:`);
    for (const diagnostic of diagnostics) {
      console.error(`  ${ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n")}`);
    }
  } else {
    console.log(`${name}: syntax OK`);
  }
}
process.exit(failed ? 1 : 0);
