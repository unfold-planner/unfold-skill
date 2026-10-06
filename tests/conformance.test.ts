// Runs the clients' real binaries, through the skill's launcher, against the contract.
//
// Each client replays the whole transcript inside its own tests, where the clock, the ids, the
// account and the running app can all be set. From outside a binary only some of that can be:
// the clock (UNFOLD_NOW), the time zone (TZ) and where the data lives; the app's version is the
// binary's own. So this replays the scenes that need nothing else (signed out, no app to tell)
// against the Linux client's binary, which runs on macOS too, and checks the Mac app's binary
// with the commands that touch no database.
//
//   UNFOLD_LINUX_BIN   the Linux client's binary (default ../unfold-omarchy/target/debug/unfold); a
//                      debug build, or one with the debug-tools feature, which follows UNFOLD_HOME
//   UNFOLD_MAC_APP     the Mac app (default ../unfold/.build/xcode/Build/Products/Debug/Unfold.app)
import { Database } from "bun:sqlite";
import { afterAll, describe, expect, test } from "bun:test";
import { existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { canonical, jsonLine, launch, repo, scratch, workspace } from "./support";

type Step = {
  name: string;
  given?: {
    now?: string;
    account?: unknown;
    linked?: unknown;
    appRunning?: boolean;
    agentsCanChange?: boolean;
  };
  args: string[];
  exit: number;
  stdout: unknown;
  stderr: unknown;
  queued?: { kind: string; id: string }[];
};
type Scene = { name: string; steps: Step[] };
type Transcript = { timeZone: string; appVersion: string; scenes: Scene[] };

const transcriptText = readFileSync(join(repo, "contract/transcript.json"), "utf8");
const help = readFileSync(join(repo, "contract/help.txt"), "utf8");

const linuxBinary =
  process.env.UNFOLD_LINUX_BIN ?? join(workspace, "unfold-omarchy/target/debug/unfold");
const macApp =
  process.env.UNFOLD_MAC_APP ??
  join(workspace, "unfold/.build/xcode/Build/Products/Debug/Unfold.app");
const hasLinuxBinary = existsSync(linuxBinary);
const hasMacApp = process.platform === "darwin" && existsSync(join(macApp, "Contents/MacOS/Unfold"));

// A scratch home with its own XDG folders, never the user's: the launcher keeps what it learns
// about the app in the cache folder, and a binary that ignores UNFOLD_HOME (a release build
// without debug-tools) keeps its database in the data folder. Each test's UNFOLD_HOME is apart.
const home = scratch("home");
const xdg = {
  XDG_CACHE_HOME: join(home, ".cache"),
  XDG_CONFIG_HOME: join(home, ".config"),
  XDG_DATA_HOME: join(home, ".local/share"),
  XDG_STATE_HOME: join(home, ".local/state"),
  XDG_RUNTIME_DIR: join(home, "runtime"),
};
mkdirSync(xdg.XDG_RUNTIME_DIR, { mode: 0o700 });
const base = { PATH: "/usr/bin:/bin", HOME: home, ...xdg };
afterAll(() => rmSync(home, { recursive: true, force: true }));

/**
 * Reads rows of a client's database. The Linux client keeps it in WAL mode, which a read-only
 * connection can't open by itself, so this one may write; the folder is the test's own.
 */
function rows<Row>(database: string, sql: string, ...values: string[]): Row[] {
  const connection = new Database(database);
  try {
    return connection.query(sql).all(...values) as Row[];
  } finally {
    connection.close();
  }
}

/**
 * A scene an outside run can set up: nobody signed in, no app running, no linked account, and the
 * app's setting letting agents make changes, as it does until the app says otherwise.
 */
function playsFromOutside(scene: Scene): boolean {
  return scene.steps.every(
    (step) =>
      !step.given?.account &&
      !step.given?.linked &&
      !step.given?.appRunning &&
      step.given?.agentsCanChange !== false,
  );
}

/**
 * Tasks made in the same instant are listed by id, and the binary's ids are its own. Once they are
 * swapped for the expected ones, each run of tasks with one creation time is put in the expected
 * ids' order; tasks made at different times stay as the binary listed them.
 */
function tiesByExpectedId(answer: any): any {
  if (!Array.isArray(answer?.tasks)) return answer;
  const tasks: { id: string; createdAt: string }[] = [];
  for (const task of answer.tasks) {
    let at = tasks.length;
    while (at > 0 && tasks[at - 1].createdAt === task.createdAt && tasks[at - 1].id < task.id) at--;
    tasks.splice(at, 0, task);
  }
  return { ...answer, tasks };
}

/** Replaces every occurrence of each key with its value. */
function swap(text: string, ids: Map<string, string>): string {
  let result = text;
  for (const [from, to] of ids) result = result.replaceAll(from, to);
  return result;
}

describe.skipIf(!hasLinuxBinary)("the Linux client's binary, through the launcher", () => {
  const transcript = JSON.parse(transcriptText.replaceAll("$PLATFORM", "linux")) as Transcript;
  const scenes = transcript.scenes.filter(playsFromOutside);

  // Else every test below would fail for that reason, and in a folder the tests can't clean.
  test("it keeps its files under UNFOLD_HOME", () => {
    const own = scratch("conformance");
    try {
      const env = { ...base, UNFOLD_SKILL_OS: "Linux", UNFOLD_BIN: linuxBinary, UNFOLD_HOME: own };

      expect(launch(["status"], env).code).toBe(0);
      const followsHome = existsSync(join(own, "data/unfold.sqlite"));
      expect({ binary: linuxBinary, followsHome }).toEqual({ binary: linuxBinary, followsHome: true });
    } finally {
      rmSync(own, { recursive: true, force: true });
    }
  });

  test("the scenes that can be played from outside are the ones expected", () => {
    expect(scenes.map((scene) => scene.name)).toEqual([
      "signed out",
      "times",
      "refusals",
      "project colors",
    ]);
  });

  for (const scene of scenes) {
    test(`plays "${scene.name}" as the contract writes it`, () => {
      const home = scratch("conformance");
      const database = join(home, "data/unfold.sqlite");
      // The ids the binary made, by the ids the transcript expects in their place.
      const made = new Map<string, string>();
      const expected = new Map<string, string>();
      let now = "";
      let seen = 0;
      try {
        for (const step of scene.steps) {
          now = step.given?.now ?? now;
          const env = {
            ...base,
            UNFOLD_SKILL_OS: "Linux",
            UNFOLD_BIN: linuxBinary,
            UNFOLD_HOME: home,
            UNFOLD_NOW: now,
            TZ: transcript.timeZone,
          };

          const run = launch(
            step.args.map((arg) => swap(arg, expected)),
            env,
          );

          const label = `${scene.name} › ${step.name}`;
          const actual = jsonLine(run.stdout) as Record<string, any> | undefined;
          // A create answers with the id it made up: from here on it stands for the expected one.
          const created = actual?.task?.id ?? actual?.project?.id;
          const wanted = (step.stdout as any)?.task?.id ?? (step.stdout as any)?.project?.id;
          if (created && wanted && !made.has(created)) {
            made.set(created, wanted);
            expected.set(wanted, created);
          }
          expect({ label, exit: run.code }).toEqual({ label, exit: step.exit });
          if (typeof step.stdout === "string") {
            expect({ label, stdout: run.stdout }).toEqual({ label, stdout: `${step.stdout}\n` });
          } else if (step.stdout === null) {
            expect({ label, stdout: run.stdout }).toEqual({ label, stdout: "" });
          } else {
            // Whether the app runs on this machine isn't the test's to say, nor which version
            // the binary was built as: the transcript's appVersion is for replays that set it.
            if (actual?.app && "running" in actual.app) {
              actual.app.running = (step.stdout as any).app.running;
            }
            if (actual?.app && "version" in actual.app) {
              expect({ label, version: actual.app.version }).toEqual({
                label,
                version: expect.stringMatching(/^\d+\.\d+/),
              });
              actual.app.version = (step.stdout as any).app.version;
            }
            const answer = tiesByExpectedId(JSON.parse(swap(JSON.stringify(actual), made)));
            expect({ label, stdout: canonical(answer) }).toEqual({
              label,
              stdout: canonical(step.stdout),
            });
          }
          const stderr = step.stderr === null ? "" : canonical(step.stderr);
          const said = run.stderr === "" ? "" : swap(canonical(jsonLine(run.stderr)), made);
          expect({ label, stderr: said }).toEqual({ label, stderr });

          // What the step queued for the app's sync: the kind and the row it is about.
          const queued = existsSync(database)
            ? rows<{ kind: string; id: string }>(
                database,
                "SELECT kind, entityId AS id FROM outbox ORDER BY seq",
              )
            : [];
          const added = queued.slice(seen).map(({ kind, id }) => ({ kind, id: made.get(id) ?? id }));
          seen = queued.length;
          expect({ label, queued: added }).toEqual({
            label,
            queued: (step.queued ?? []).map(({ kind, id }) => ({ kind, id })),
          });
        }
      } finally {
        rmSync(home, { recursive: true, force: true });
      }
    });
  }

  test("what it saves is there for the next command, and for the app", () => {
    const home = scratch("conformance");
    const env = {
      ...base,
      UNFOLD_SKILL_OS: "Linux",
      UNFOLD_BIN: linuxBinary,
      UNFOLD_HOME: home,
      TZ: "America/New_York",
    };
    try {
      const added = jsonLine(
        launch(["tasks", "add", "--title", "Kept", "--start", "2026-10-01T10:00"], env).stdout,
      ) as any;
      const listed = jsonLine(launch(["tasks", "list"], env).stdout) as any;
      const [row] = rows<{ title: string; startsAt: number; endsAt: number }>(
        join(home, "data/unfold.sqlite"),
        "SELECT title, startsAt, endsAt FROM todo WHERE id = ?",
        added.task.id,
      );

      expect(listed.tasks).toEqual([added.task]);
      // The computer's zone, from TZ: 10:00 in New York, and half an hour by default.
      expect(added.task.sessions).toEqual([
        { start: "2026-10-01T10:00:00-04:00", end: "2026-10-01T10:30:00-04:00", allDay: false },
      ]);
      expect(row).toEqual({
        title: "Kept",
        startsAt: Date.parse("2026-10-01T14:00:00Z"),
        endsAt: Date.parse("2026-10-01T14:30:00Z"),
      });
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("it writes nothing but its one line, on the right stream", () => {
    const home = scratch("conformance");
    const env = { ...base, UNFOLD_SKILL_OS: "Linux", UNFOLD_BIN: linuxBinary, UNFOLD_HOME: home };
    try {
      const ok = launch(["status"], env);
      const bad = launch(["tasks", "show", "nope"], env);

      expect(ok.stderr).toBe("");
      expect(ok.stdout.trimEnd().split("\n")).toHaveLength(1);
      expect(bad.stdout).toBe("");
      expect(bad.stderr.trimEnd().split("\n")).toHaveLength(1);
      expect(bad.code).toBe(1);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });
});

// The Mac app's binary runs in the app's sandbox, so its database can't be put in a folder of the
// test's. These commands open none: they check the launcher against the real app, and the binary's
// streams and exit codes. The rest of the contract is the app's own transcript test.
describe.skipIf(!hasMacApp)("the Mac app's binary, through the launcher", () => {
  const env = { ...base, UNFOLD_SKILL_OS: "Darwin", UNFOLD_APP: macApp };

  test("version", () => {
    const run = launch(["version"], env);

    expect(run.code).toBe(0);
    expect(run.stderr).toBe("");
    const version = jsonLine(run.stdout) as any;
    expect(version.contract).toBe(1);
    expect(version.app.platform).toBe("macos");
    expect(version.app.version).toMatch(/^\d+\.\d+/);
  });

  test("help is the contract's text", () => {
    expect(launch(["help"], env)).toEqual({ code: 0, stdout: help, stderr: "" });
  });

  test("a command that can't be read fails on stderr with exit code 2, before any database", () => {
    const transcript = JSON.parse(transcriptText) as Transcript;
    const refusals = transcript.scenes.find((scene) => scene.name === "refusals")?.steps ?? [];
    const usage = refusals.filter((step) => step.exit === 2);
    expect(usage.length).toBeGreaterThan(15);

    for (const step of usage) {
      const run = launch(step.args, env);

      expect({ step: step.name, code: run.code, stdout: run.stdout }).toEqual({
        step: step.name,
        code: 2,
        stdout: "",
      });
      expect({ step: step.name, stderr: canonical(jsonLine(run.stderr)) }).toEqual({
        step: step.name,
        stderr: canonical(step.stderr),
      });
    }
  });
});

test("at least one client's binary was there to check", () => {
  // `scripts/check.sh` builds the Linux client first; a run with neither checked nothing here.
  if (!process.env.UNFOLD_ALLOW_NO_CLIENTS) {
    expect({ hasLinuxBinary, hasMacApp }).not.toEqual({ hasLinuxBinary: false, hasMacApp: false });
  }
});
