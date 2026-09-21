// Drives pi/extensions/compaction-bound.ts against synthetic conversations.
// Run by scripts/smoke_compaction.sh inside the pinned image, where
// @earendil-works/pi-coding-agent resolves.
import assert from "node:assert/strict";
import { serializeConversation, convertToLlm } from "@earendil-works/pi-coding-agent";
import { truncate, boundMessage, fitMessages, isDeterministic } from "./compaction-bound.ts";

function assistant(thinkingChars, textChars, argChars) {
  return {
    role: "assistant",
    content: [
      { type: "thinking", thinking: "t".repeat(thinkingChars) },
      { type: "text", text: "x".repeat(textChars) },
      { type: "toolCall", id: "c1", name: "write", arguments: { path: "a.py", content: "y".repeat(argChars) } },
    ],
    timestamp: 0,
  };
}

function toolResult(chars) {
  return { role: "toolResult", toolCallId: "c1", content: [{ type: "text", text: "r".repeat(chars) }], timestamp: 0 };
}

// truncate keeps the head and says how much went missing.
assert.equal(truncate("abc", 10), "abc");
const cut = truncate("a".repeat(100), 10);
assert.ok(cut.startsWith("a".repeat(10)));
assert.ok(cut.includes("90 characters withheld"));
assert.ok(cut.length < 100);

// boundMessage caps thinking, text, and tool-call arguments, and leaves the
// block kinds, their order, and the tool name and small arguments alone.
const bounded = boundMessage(assistant(200000, 200000, 200000));
assert.deepEqual(bounded.content.map((b) => b.type), ["thinking", "text", "toolCall"]);
assert.ok(bounded.content[0].thinking.length < 1200, bounded.content[0].thinking.length);
assert.ok(bounded.content[1].text.length < 4200, bounded.content[1].text.length);
assert.equal(bounded.content[2].name, "write");
assert.equal(bounded.content[2].arguments.path, "a.py");
assert.ok(bounded.content[2].arguments.content.length < 1200);

// A message already inside every cap comes back untouched, by identity.
const small = assistant(10, 10, 10);
assert.equal(boundMessage(small), small);

// The real failure: 200 turns of maximal thinking. Pi would serialize this at
// tens of millions of characters; the bound has to land under budget.
const huge = [];
for (let i = 0; i < 200; i += 1) {
  huge.push(assistant(120000, 8000, 60000));
  huge.push(toolResult(40000));
}
const rawChars = serializeConversation(convertToLlm(huge)).length;
const budget = 184090; // what a 131072-token window yields in the study config
const fitted = fitMessages(huge, budget);
assert.ok(rawChars > 20000000, `raw ${rawChars}`);
assert.ok(fitted.chars <= budget, `fitted ${fitted.chars} > ${budget}`);
assert.ok(fitted.dropped > 0, "expected the drop path to run");
assert.ok(fitted.messages.length > 1, "must keep the most recent messages");
// The oldest messages go first and the summarizer is told they are missing.
const notice = serializeConversation(convertToLlm([fitted.messages[0]]));
assert.ok(notice.includes(`${fitted.dropped} earlier messages were withheld`), notice.slice(0, 200));

// Truncation alone carries a span of the size compaction actually sees. The
// span runs from the previous cut to the new one, which keepRecentTokens holds
// to tens of thousands of tokens; resuming the real dead session produced 32
// messages serializing to 19588 characters. These 32 are each maximal, so the
// span is several times denser than that, and still nothing is dropped.
const ordinary = [];
for (let i = 0; i < 16; i += 1) {
  ordinary.push(assistant(30000, 8000, 60000));
  ordinary.push(toolResult(40000));
}
const plain = fitMessages(ordinary, budget);
assert.equal(plain.dropped, 0);
assert.equal(plain.messages.length, ordinary.length);
assert.ok(plain.chars <= budget, `ordinary ${plain.chars}`);

// An empty span is left alone rather than turned into a notice.
assert.deepEqual(fitMessages([], budget), { messages: [], dropped: 0, chars: 0 });

console.log(JSON.stringify({
  raw_chars: rawChars,
  fitted_chars: fitted.chars,
  dropped: fitted.dropped,
  kept: fitted.messages.length,
  ordinary_chars: plain.chars,
}));
console.log("compaction bound: ok");

// A size rejection must be recognized in either server's own words, or the
// extension spends its retries on a request that cannot succeed. The SGLang
// strings are verbatim from sglang/srt/managers/tokenizer_manager.py 0.5.20.
for (const wording of [
  "exceed_context_size_error",
  "the request exceeds the available context size",
  "The input (140000 tokens) is longer than the model's context length (131072 tokens).",
  "Requested token count exceeds the model's maximum context length of 131072 tokens.",
]) {
  assert.equal(isDeterministic(wording), true, `unrecognized size error: ${wording}`);
}
for (const wording of ["terminated", "fetch failed", "socket hang up", "503 Service Unavailable"]) {
  assert.equal(isDeterministic(wording), false, `a transient error was treated as final: ${wording}`);
}
console.log("size errors recognized for llama.cpp and SGLang; transient errors left retryable");
