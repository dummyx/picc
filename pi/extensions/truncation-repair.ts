import type {
  ExtensionAPI,
  MessageEndEvent,
} from "@earendil-works/pi-coding-agent";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

// When the model reaches its output token limit while still reasoning, the
// reply ends with no tool call and no text: a whole round produces nothing.
// The unfinished reasoning then stays in the conversation, and the next reply
// is cut off the same way. Across 3217 assistant messages in v10-v15 the plain
// rate of a cut-off reply is 5.8%, but after a cut-off reply it is 64.7% —
// thirty times higher. A run that enters that state produces nothing for the
// rest of its budget, which is how `v15-sql-python-r1` spent five rounds
// restarting the same engine design from the beginning.
//
// The unfinished reasoning is an artifact of the harness's own output cap, so
// the harness cleans it up: keep a short head of it, state plainly that the
// reply was cut off, and drop the rest. The note says what happened and
// nothing about what to do next — the agent's choices stay its own, and the
// same repair applies in every condition.

const ARTIFACTS = process.env.PICC_ARTIFACTS ?? "/run-artifacts";
const EVENT_PATH = `${ARTIFACTS}/extension-events.jsonl`;

// Enough of the reasoning to carry its intent into the next round, far too
// little to read as an argument still in progress.
const KEEP_THINKING_CHARS = 1500;

function appendEvent(record: Record<string, unknown>): void {
  try {
    mkdirSync(dirname(EVENT_PATH), { recursive: true });
    appendFileSync(
      EVENT_PATH,
      JSON.stringify({ timestamp: new Date().toISOString(), ...record }) + "\n",
      "utf8",
    );
  } catch {
    // Observability must not terminate the agent process.
  }
}

type Block = { type?: unknown; text?: unknown; thinking?: unknown };

function blocksOf(message: unknown): Block[] | undefined {
  const content = (message as { content?: unknown })?.content;
  return Array.isArray(content) ? (content as Block[]) : undefined;
}

/**
 * The reasoning kept, and the note that replaces the rest. Exported for
 * scripts/truncation_probe.mjs; Pi only uses the default export.
 */
export function repairedContent(thinking: string): Block[] {
  const kept = thinking.slice(0, KEEP_THINKING_CHARS);
  const dropped = thinking.length - kept.length;
  const note =
    `[This reply reached the output token limit while still reasoning, so it ` +
    `ended before producing any output. The reasoning above is its first ` +
    `${kept.length} characters; the remaining ${dropped} were discarded and ` +
    `cannot be recovered.]`;
  return [
    { type: "thinking", thinking: kept },
    { type: "text", text: note },
  ];
}

/** Whether a finished assistant message is one of the wasted, unfinished ones. */
export function needsRepair(message: unknown): string | undefined {
  const typed = message as { role?: unknown; stopReason?: unknown };
  if (typed?.role !== "assistant" || typed?.stopReason !== "length") return undefined;
  const blocks = blocksOf(message);
  if (!blocks) return undefined;
  // A reply that called a tool or said something did useful work even though
  // it was cut off; only the ones that produced nothing are repaired.
  if (blocks.some((block) => block.type === "toolCall")) return undefined;
  const text = blocks
    .filter((block) => block.type === "text" && typeof block.text === "string")
    .map((block) => block.text as string)
    .join("")
    .trim();
  if (text.length > 0) return undefined;
  const thinking = blocks
    .filter((block) => block.type === "thinking" && typeof block.thinking === "string")
    .map((block) => block.thinking as string)
    .join("\n");
  return thinking.length > KEEP_THINKING_CHARS ? thinking : undefined;
}

export default function (pi: ExtensionAPI): void {
  // The harness refuses to continue a run without this line.
  appendEvent({ event: "truncation_repair_loaded" });

  pi.on("message_end", (event: MessageEndEvent) => {
    const thinking = needsRepair(event.message);
    if (thinking === undefined) return;
    appendEvent({
      event: "truncation_repaired",
      thinking_chars: thinking.length,
      kept_chars: KEEP_THINKING_CHARS,
    });
    // stopReason stays "length": Pi keys its own overflow-recovery bookkeeping
    // on it, and this repair is about what the next round reads, not about
    // Pi's control flow.
    return {
      message: { ...(event.message as object), content: repairedContent(thinking) },
    } as { message: MessageEndEvent["message"] };
  });
}
