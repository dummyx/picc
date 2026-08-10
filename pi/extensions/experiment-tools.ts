import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
import { spawn } from "node:child_process";

const ARTIFACTS = process.env.PICC_ARTIFACTS ?? "/run-artifacts";
const STATE_PATH = process.env.PICC_RUN_STATE ?? `${ARTIFACTS}/state.json`;
const EVENT_PATH = `${ARTIFACTS}/extension-events.jsonl`;
const MAX_STAGE = Number.parseInt(process.env.PICC_MAX_STAGE ?? "10", 10);

function appendEvent(record: Record<string, unknown>): void {
  try {
    mkdirSync(dirname(EVENT_PATH), { recursive: true });
    appendFileSync(
      EVENT_PATH,
      JSON.stringify({ timestamp: new Date().toISOString(), ...record }) + "\n",
      "utf8",
    );
  } catch {
    // Experimental logging must not take down Pi.
  }
}

async function run(
  command: string,
  args: string[],
  signal?: AbortSignal,
  timeoutMs = 15 * 60 * 1000,
): Promise<{ code: number; stdout: string; stderr: string }> {
  return await new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: "/workspace",
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    const maxBytes = 8 * 1024 * 1024;
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      if (stdout.length < maxBytes) stdout += chunk.slice(0, maxBytes - stdout.length);
    });
    child.stderr.on("data", (chunk: string) => {
      if (stderr.length < maxBytes) stderr += chunk.slice(0, maxBytes - stderr.length);
    });

    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      setTimeout(() => child.kill("SIGKILL"), 2000).unref();
    }, timeoutMs);

    const abort = () => child.kill("SIGTERM");
    signal?.addEventListener("abort", abort, { once: true });

    child.on("error", (error) => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      resolve({ code: code ?? 128, stdout, stderr });
    });
  });
}

type EvaluationSummary = {
  score?: number;
  passed?: number;
  failed?: number;
  total?: number;
  build_ok?: boolean;
  stages?: Record<string, { score?: number; passed?: number; total?: number }>;
  failures?: Array<{ id?: string; failure_type?: string; detail?: string }>;
  error?: string;
};

function renderSummary(summary: EvaluationSummary, outputPath: string): string {
  const lines: string[] = [];
  lines.push(
    `Visible evaluation: score=${Number(summary.score ?? 0).toFixed(4)}, ` +
      `passed=${summary.passed ?? 0}/${summary.total ?? 0}, build_ok=${Boolean(summary.build_ok)}`,
  );
  if (summary.stages) {
    for (const [stage, row] of Object.entries(summary.stages)) {
      lines.push(
        `  stage ${stage}: score=${Number(row.score ?? 0).toFixed(4)}, ` +
          `passed=${row.passed ?? 0}/${row.total ?? 0}`,
      );
    }
  }
  const failures = summary.failures ?? [];
  if (failures.length > 0) {
    lines.push("Representative failures:");
    for (const failure of failures.slice(0, 8)) {
      const detail = failure.detail ? ` — ${failure.detail.slice(0, 500)}` : "";
      lines.push(`  - ${failure.id ?? "unknown"}: ${failure.failure_type ?? "failed"}${detail}`);
    }
  }
  if (summary.error) lines.push(`Evaluator error: ${summary.error}`);
  lines.push(`Full machine-readable result: ${outputPath} (harness-owned; do not edit).`);
  return lines.join("\n");
}

export default function experimentTools(pi: ExtensionAPI) {
  pi.registerTool({
    name: "test_visible",
    label: "Run visible PiCC tests",
    description:
      "Build PiCC and run the controlled visible behavioral tests. Returns concise stage scores and representative failures.",
    promptSnippet: "Run controlled visible PiCC tests, optionally by stage or test ID",
    promptGuidelines: [
      "Use test_visible after meaningful compiler changes; prefer a focused stage before a broad run.",
      "Do not invoke an external C compiler directly; test_visible owns reference assembly/link execution.",
    ],
    parameters: Type.Object({
      stage: Type.Optional(Type.Integer({ minimum: 1, maximum: 10 })),
      latestOnly: Type.Optional(Type.Boolean()),
      testId: Type.Optional(Type.String({ maxLength: 500 })),
    }),
    async execute(toolCallId, params, signal) {
      const stage = Math.min(params.stage ?? MAX_STAGE, MAX_STAGE);
      const safeId = toolCallId.replace(/[^a-zA-Z0-9_.-]/g, "_");
      const outputPath = `${ARTIFACTS}/tool-evaluations/${safeId}.json`;
      const args = [
        "/opt/picc-eval/evaluate.py",
        "--workspace",
        "/workspace",
        "--tests-root",
        "/visible-tests",
        "--manifest",
        "/visible-tests/manifest.json",
        "--max-stage",
        String(stage),
        "--output",
        outputPath,
        "--summary-json",
      ];
      if (params.latestOnly) args.push("--latest-only");
      if (params.testId) args.push("--test-id", params.testId);

      appendEvent({ event: "test_visible_start", toolCallId, params, outputPath });
      const result = await run("python3", args, signal);
      let summary: EvaluationSummary;
      try {
        summary = JSON.parse(result.stdout.trim()) as EvaluationSummary;
      } catch {
        summary = {
          score: 0,
          build_ok: false,
          error: `Evaluator returned non-JSON output (exit ${result.code}): ${result.stderr.slice(0, 2000)}`,
        };
      }
      appendEvent({
        event: "test_visible_end",
        toolCallId,
        exitCode: result.code,
        summary,
        stderr: result.stderr.slice(0, 4000),
      });
      if (result.code !== 0 && !summary.error) {
        summary.error = `Evaluator exited ${result.code}: ${result.stderr.slice(0, 2000)}`;
      }
      return {
        content: [{ type: "text", text: renderSummary(summary, outputPath) }],
        details: summary,
      };
    },
  });

  pi.registerTool({
    name: "experiment_status",
    label: "Inspect experiment status",
    description: "Read the current fixed budget, round number, elapsed time, and last harness evaluation.",
    promptSnippet: "Inspect fixed experiment budget and last harness-visible score",
    parameters: Type.Object({}),
    async execute() {
      try {
        const state = JSON.parse(readFileSync(STATE_PATH, "utf8")) as Record<string, unknown>;
        return {
          content: [{ type: "text", text: JSON.stringify(state, null, 2) }],
          details: state,
        };
      } catch (error) {
        return {
          content: [
            {
              type: "text",
              text: `No harness state is available yet: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
          details: {},
        };
      }
    },
  });

  pi.on("session_before_compact", async (event) => {
    appendEvent({
      event: "session_before_compact",
      reason: event.reason,
      willRetry: event.willRetry,
      tokensBefore: event.preparation.tokensBefore,
      firstKeptEntryId: event.preparation.firstKeptEntryId,
    });
  });

  pi.on("session_compact", async (event) => {
    appendEvent({
      event: "session_compact",
      reason: event.reason,
      willRetry: event.willRetry,
      fromExtension: event.fromExtension,
      compactionEntryId: (event.compactionEntry as { id?: string } | undefined)?.id,
    });
  });

  pi.on("after_provider_response", async (event) => {
    if (event.status === 429 || event.status >= 500) {
      appendEvent({
        event: "provider_response_error",
        status: event.status,
        retryAfter: event.headers["retry-after"],
      });
    }
  });
}
