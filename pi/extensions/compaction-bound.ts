import type {
  ExtensionAPI,
  ExtensionContext,
  SessionBeforeCompactEvent,
} from "@earendil-works/pi-coding-agent";
import {
  compact,
  convertToLlm,
  serializeConversation,
} from "@earendil-works/pi-coding-agent";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

// Pi summarizes a conversation by serializing it to text and sending that text
// to the model in one request. `serializeConversation` truncates tool results
// to 2000 characters, on the stated assumption that tool results dominate a
// conversation's size. Nothing else is truncated: assistant thinking blocks and
// tool-call arguments (which carry whole file bodies for `write`) go in whole.
//
// That assumption does not hold here. The agent runs a local reasoning model at
// the highest thinking level with an output cap of 32768 tokens, so a round of
// planning with few tool calls is mostly thinking. The summarization request
// then outgrows the context window and compaction fails; the session cannot
// shed context, so every later round fails the same way and the run is dead.
// Across this repository's runs that produced requests of 132k to 401k tokens
// against a 131072-token window.
//
// A second failure appears when the summarization call itself is allowed to
// think: its output budget is a fraction of `reserveTokens`, thinking is spent
// from that same budget, and the response stops on length before the summary
// is written. Pi refuses a length-stopped summary, so compaction fails again.
//
// This extension takes over compaction and fixes both: it bounds what goes into
// the summarization request, then hands the bounded work back to Pi's own
// `compact()` with thinking switched off for that one call. Everything else,
// including the prompts, the split-turn handling, and the file-operation lists,
// stays Pi's.

const ARTIFACTS = process.env.PICC_ARTIFACTS ?? "/run-artifacts";
const EVENT_PATH = `${ARTIFACTS}/extension-events.jsonl`;

// Per-block caps, in characters. Thinking is cut hardest: the summary needs the
// agent's intent, which is in the opening sentences, not the whole derivation.
const THINKING_CHARS = 1000;
const TEXT_CHARS = 4000;
const TOOL_ARGUMENT_CHARS = 1000;

// Pi estimates tokens as characters/4 and calls that conservative. Serialized
// source code runs denser than prose, so budget at characters/3 instead.
const CHARS_PER_TOKEN = 3;
// System prompt, summarization instructions, and the wrapping tags.
const PROMPT_OVERHEAD_TOKENS = 2048;
// Leave a quarter of the computed room unused: the estimate is a heuristic and
// the cost of overshooting is a dead session.
const BUDGET_SAFETY = 0.75;
// Share of the budget reserved for the previous summary on repeat compactions.
const PREVIOUS_SUMMARY_SHARE = 0.15;

const MAX_ATTEMPTS = 3;
const RETRY_DELAY_MS = 2000;

type Preparation = SessionBeforeCompactEvent["preparation"];
type Message = Preparation["messagesToSummarize"][number];

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

export function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  const dropped = text.length - maxChars;
  return `${text.slice(0, maxChars)}\n[... ${dropped} characters withheld from summarization]`;
}

function boundArguments(args: unknown): unknown {
  if (args === null || typeof args !== "object" || Array.isArray(args)) return args;
  const bounded: Record<string, unknown> = {};
  let changed = false;
  for (const [key, value] of Object.entries(args as Record<string, unknown>)) {
    if (typeof value === "string") {
      const capped = truncate(value, TOOL_ARGUMENT_CHARS);
      changed = changed || capped !== value;
      bounded[key] = capped;
      continue;
    }
    let encoded: string;
    try {
      encoded = JSON.stringify(value) ?? "";
    } catch {
      changed = true;
      bounded[key] = "[unserializable argument withheld from summarization]";
      continue;
    }
    if (encoded.length > TOOL_ARGUMENT_CHARS) {
      changed = true;
      bounded[key] = `[${encoded.length} characters withheld from summarization]`;
      continue;
    }
    bounded[key] = value;
  }
  // Returning the original when nothing was capped lets boundMessage leave the
  // message itself untouched, which is what keeps unchanged spans cheap.
  return changed ? bounded : args;
}

/** Cap every oversized part of one message. Block kinds and order are kept. */
export function boundMessage(message: Message): Message {
  const content = (message as { content?: unknown }).content;
  if (!Array.isArray(content)) return message;
  let changed = false;
  const bounded = content.map((block) => {
    if (block === null || typeof block !== "object") return block;
    const typed = block as Record<string, unknown>;
    if (typed.type === "thinking" && typeof typed.thinking === "string") {
      const thinking = truncate(typed.thinking, THINKING_CHARS);
      if (thinking === typed.thinking) return block;
      changed = true;
      return { ...typed, thinking };
    }
    if (typed.type === "text" && typeof typed.text === "string") {
      const text = truncate(typed.text, TEXT_CHARS);
      if (text === typed.text) return block;
      changed = true;
      return { ...typed, text };
    }
    if (typed.type === "toolCall") {
      const args = boundArguments(typed.arguments);
      if (args === typed.arguments) return block;
      changed = true;
      return { ...typed, arguments: args };
    }
    return block;
  });
  if (!changed) return message;
  return { ...(message as object), content: bounded } as Message;
}

function serializedLength(messages: Message[]): number {
  return serializeConversation(convertToLlm(messages)).length;
}

function omissionNotice(count: number): Message {
  return {
    role: "user",
    content: [
      {
        type: "text",
        text:
          `[${count} earlier messages were withheld so this summarization request ` +
          `fits the model's context window. Summarize what remains.]`,
      },
    ],
    timestamp: Date.now(),
  } as unknown as Message;
}

/**
 * Cap each message, then drop the oldest ones until the serialized text fits.
 * Exported for scripts/smoke_compaction.sh; Pi only uses the default export.
 * Dropping is safe because the result is serialized to plain text, so a tool
 * result never needs its tool call to stay valid.
 */
export function fitMessages(
  messages: Message[],
  budgetChars: number,
): { messages: Message[]; dropped: number; chars: number } {
  if (messages.length === 0) return { messages, dropped: 0, chars: 0 };
  let kept = messages.map(boundMessage);
  let chars = serializedLength(kept);
  let dropped = 0;
  while (chars > budgetChars && kept.length > 1) {
    const step = Math.max(1, Math.ceil(kept.length / 10));
    kept = kept.slice(step);
    dropped += step;
    chars = serializedLength(kept);
  }
  if (dropped > 0) {
    kept = [omissionNotice(dropped), ...kept];
    chars = serializedLength(kept);
  }
  return { messages: kept, dropped, chars };
}

/**
 * The one error retrying cannot fix: the request is unchanged, so a provider
 * that rejected it for size will reject it again. Everything else, notably a
 * dropped stream, is worth another attempt.
 */
function isDeterministic(message: string): boolean {
  return /exceed_context_size_error|exceeds the available context/.test(message);
}

function isAbort(error: unknown): boolean {
  if (error === null || typeof error !== "object") return false;
  const name = (error as { name?: unknown }).name;
  return name === "AbortError";
}

function delay(ms: number, signal: AbortSignal | undefined): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
  });
}

export default function (pi: ExtensionAPI): void {
  // The harness refuses to continue a run without this line: a value import
  // that fails to resolve would leave the extension unloaded and the defect
  // back in place, silently.
  appendEvent({ event: "compaction_bound_loaded" });

  pi.on("session_before_compact", async (event: SessionBeforeCompactEvent, ctx: ExtensionContext) => {
    const model = ctx.model;
    if (!model) return;

    const preparation = event.preparation;
    const settings = preparation.settings;

    // Mirror Pi's own output budget for the summarization call, so the input
    // budget below is the room that actually remains.
    const contextWindow = model.contextWindow > 0 ? model.contextWindow : 131072;
    const modelMax = model.maxTokens > 0 ? model.maxTokens : contextWindow;
    const summaryTokens = Math.min(Math.floor(0.8 * settings.reserveTokens), modelMax);
    const inputTokens = Math.max(
      4096,
      Math.floor((contextWindow - summaryTokens - PROMPT_OVERHEAD_TOKENS) * BUDGET_SAFETY),
    );
    const budgetChars = inputTokens * CHARS_PER_TOKEN;
    const previousBudget = Math.floor(budgetChars * PREVIOUS_SUMMARY_SHARE);
    const conversationBudget = budgetChars - previousBudget;

    const history = fitMessages(preparation.messagesToSummarize, conversationBudget);
    const prefix = fitMessages(preparation.turnPrefixMessages, conversationBudget);
    const previousSummary =
      typeof preparation.previousSummary === "string"
        ? truncate(preparation.previousSummary, previousBudget)
        : preparation.previousSummary;

    const bounded = {
      ...preparation,
      messagesToSummarize: history.messages,
      turnPrefixMessages: prefix.messages,
      previousSummary,
    };

    const auth = await ctx.modelRegistry.getApiKeyAndHeaders(model);
    const resolved = auth.ok ? auth : undefined;
    const requestModel = resolved?.baseUrl ? { ...model, baseUrl: resolved.baseUrl } : model;

    const base = {
      event: "compaction_bound",
      reason: event.reason,
      split_turn: preparation.isSplitTurn,
      tokens_before: preparation.tokensBefore,
      budget_chars: conversationBudget,
      history_messages_in: preparation.messagesToSummarize.length,
      history_messages_out: history.messages.length,
      history_dropped: history.dropped,
      history_chars: history.chars,
      prefix_messages_in: preparation.turnPrefixMessages.length,
      prefix_messages_out: prefix.messages.length,
      prefix_dropped: prefix.dropped,
      prefix_chars: prefix.chars,
    };

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
      try {
        const result = await compact(
          bounded,
          requestModel,
          resolved?.apiKey,
          resolved?.headers,
          event.customInstructions,
          event.signal,
          // Thinking off: the summarization response has a fixed token budget
          // and a thinking model spends it before writing the summary.
          "off",
          undefined,
          resolved?.env,
        );
        appendEvent({ ...base, outcome: "ok", attempt, summary_chars: result.summary.length });
        return { compaction: result };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (isAbort(error) || event.signal.aborted) {
          appendEvent({ ...base, outcome: "aborted", attempt, error: message });
          return;
        }
        if (attempt === MAX_ATTEMPTS || isDeterministic(message)) {
          // Hand back to Pi's default path rather than failing the compaction
          // here: the outcome is no worse, and the failure stays Pi's to report.
          appendEvent({ ...base, outcome: "failed", attempt, error: message });
          return;
        }
        appendEvent({ ...base, outcome: "retry", attempt, error: message });
        await delay(RETRY_DELAY_MS * attempt, event.signal);
      }
    }
    return;
  });
}
