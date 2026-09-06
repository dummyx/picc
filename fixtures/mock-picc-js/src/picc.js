// Mock PiCC used only by the evaluator smoke test: accepts `int main(void) { return N; }`.
"use strict";
const fs = require("node:fs");

function parse(source) {
  const match = /^\s*int\s+main\s*\(\s*void\s*\)\s*\{\s*return\s+(\d+)\s*;\s*\}\s*$/.exec(source);
  if (match === null) return undefined;
  return { value: Number.parseInt(match[1], 10) };
}

function main(argv) {
  if (argv.length !== 3 || argv[1] !== "-o") {
    console.error("usage: picc INPUT.c -o OUTPUT.s");
    return 1;
  }
  const program = parse(fs.readFileSync(argv[0], "utf8"));
  if (program === undefined) {
    console.error("unsupported or malformed program");
    return 1;
  }
  fs.writeFileSync(argv[2], `.globl main\nmain:\n  mov $${program.value}, %eax\n  ret\n`);
  return 0;
}

process.exitCode = main(process.argv.slice(2));
