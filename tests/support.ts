// What the tests share: paths, a way to run the launcher, and JSON compared strictly.
import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

export const repo = join(import.meta.dir, "..");
export const workspace = join(repo, "..");
export const launcher = join(repo, "skills/unfold/scripts/unfold");

export type Run = { code: number; stdout: string; stderr: string };

/** Runs the launcher with exactly `env` (nothing inherited), under `shell`. */
export function launch(args: string[], env: Record<string, string>, shell = "sh"): Run {
  const result = spawnSync(shell, [launcher, ...args], { env, encoding: "utf8" });
  if (result.error) throw result.error;
  return { code: result.status ?? -1, stdout: result.stdout, stderr: result.stderr };
}

/** The shells the launcher must run under: `sh`, and `dash` where there is one. */
export const shells = ["sh", ...(existsSync("/bin/dash") ? ["/bin/dash"] : [])];

export function scratch(prefix: string): string {
  return mkdtempSync(join(tmpdir(), `unfold-skill-${prefix}-`));
}

export function writeExecutable(path: string, script: string): string {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, script);
  chmodSync(path, 0o755);
  return path;
}

/** JSON as text two values share only when they are the same: keys sorted, `true` apart from 1. */
export function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const fields = Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([key, field]) => `${JSON.stringify(key)}:${canonical(field)}`);
    return `{${fields.join(",")}}`;
  }
  return JSON.stringify(value ?? null);
}

/** The one JSON line a stream holds, or `undefined` when it holds something else. */
export function jsonLine(text: string): unknown {
  const lines = text.split("\n").filter((line) => line !== "");
  if (lines.length !== 1) return undefined;
  try {
    return JSON.parse(lines[0]);
  } catch {
    return undefined;
  }
}
