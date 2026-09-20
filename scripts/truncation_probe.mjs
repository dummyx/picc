// Drives pi/extensions/truncation-repair.ts against synthetic replies.
// Run by scripts/smoke_extensions.sh inside the pinned image.
import assert from "node:assert/strict";
import { needsRepair, repairedContent } from "./truncation-repair.ts";

const long = "t".repeat(110000);

function reply(stopReason, blocks) {
  return { role: "assistant", stopReason, content: blocks, timestamp: 0 };
}
const thinking = (text) => ({ type: "thinking", thinking: text });
const text = (t) => ({ type: "text", text: t });
const toolCall = (name) => ({ type: "toolCall", id: "c1", name, arguments: {} });

// The wasted reply: cut off at the output limit with nothing to show for it.
assert.equal(needsRepair(reply("length", [thinking(long)])), long);

// Replies that produced something are left alone even when cut off, because
// the tool call or the text is real work the next round needs.
assert.equal(needsRepair(reply("length", [thinking(long), toolCall("write")])), undefined);
assert.equal(needsRepair(reply("length", [thinking(long), text("Writing pisql.py now.")])), undefined);

// So is a reply that ended normally, however much it thought.
assert.equal(needsRepair(reply("toolUse", [thinking(long)])), undefined);
assert.equal(needsRepair(reply("stop", [thinking(long)])), undefined);

// And so is anything that is not an assistant reply, or has nothing to trim.
assert.equal(needsRepair({ role: "user", stopReason: "length", content: [text("hi")] }), undefined);
assert.equal(needsRepair(reply("length", [thinking("short")])), undefined);
assert.equal(needsRepair(reply("length", [])), undefined);
assert.equal(needsRepair(reply("length", undefined)), undefined);
assert.equal(needsRepair(undefined), undefined);

// Whitespace-only text is not output, so that reply is still wasted.
assert.equal(needsRepair(reply("length", [thinking(long), text("  \n ")])), long);

// The repair keeps a readable head, says what happened, and is far smaller.
const repaired = repairedContent(long);
assert.deepEqual(repaired.map((b) => b.type), ["thinking", "text"]);
assert.equal(repaired[0].thinking.length, 1500);
assert.ok(repaired[0].thinking === long.slice(0, 1500));
assert.ok(repaired[1].text.includes("output token limit"));
assert.ok(repaired[1].text.includes("108500"), repaired[1].text);
const before = long.length;
const after = repaired.reduce((n, b) => n + (b.thinking ?? b.text ?? "").length, 0);
assert.ok(after < before / 50, `${after} vs ${before}`);

console.log(JSON.stringify({ before, after, ratio: Number((before / after).toFixed(1)) }));
console.log("truncation repair: ok");
