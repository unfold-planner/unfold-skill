// The launcher finds the installed app, refuses one without a command line, and hands the
// arguments on unchanged. Fake apps stand in for Unfold: they record how they were called.
import { describe, expect, test } from "bun:test";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { jsonLine, launch, scratch, shells, writeExecutable } from "./support";

const onMac = process.platform === "darwin";

/** A fake binary: appends its arguments, NUL-separated and one call per line, to `log`. */
function recorder(log: string, body = 'printf \'{"ok":true}\\n\''): string {
  return `#!/bin/sh
{ for arg in "$@"; do printf '%s\\0' "$arg"; done; printf '\\n'; } >> "${log}"
${body}
`;
}

/** The calls a recorder logged, each as its arguments. */
function calls(log: string): string[][] {
  if (!existsSync(log)) return [];
  return readFileSync(log, "utf8")
    .split("\0\n")
    .filter((call) => call !== "")
    .map((call) => call.split("\0"));
}

function plist(contract?: string): string {
  const key = contract === undefined ? "" : `<key>UnfoldCLIContract</key>${contract}`;
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>com.unfoldplanner.mac</string>
${key}
</dict></plist>
`;
}

type Stage = { root: string; log: string; bin: string; env: Record<string, string> };

/** A scratch computer: an empty root and home, and a PATH with only the system's tools. */
function stage(os: string): Stage {
  const root = scratch("launcher");
  const bin = join(root, "bin");
  mkdirSync(bin);
  mkdirSync(join(root, "home"));
  if (!onMac) {
    // Off macOS there is no plutil: this one reads the one key the launcher asks for.
    writeExecutable(
      join(bin, "plutil"),
      `#!/bin/sh
value=$(sed -n 's:.*<key>UnfoldCLIContract</key><integer>\\([^<]*\\)</integer>.*:\\1:p' "$6")
[ -n "$value" ] || exit 1
printf '%s\\n' "$value"
`,
    );
  }
  return {
    root,
    log: join(root, "calls.log"),
    bin,
    env: {
      PATH: `${bin}:/usr/bin:/bin`,
      HOME: join(root, "home"),
      UNFOLD_SKILL_OS: os,
      UNFOLD_SKILL_ROOT: root,
    },
  };
}

/** Installs a fake Unfold.app under `folder` and returns its path. */
function installMacApp(stage: Stage, folder: string, contract?: string, body?: string): string {
  const app = join(folder, "Unfold.app");
  writeExecutable(join(app, "Contents/MacOS/Unfold"), recorder(stage.log, body));
  writeFileSync(join(app, "Contents/Info.plist"), plist(contract));
  return app;
}

const error = (run: { stderr: string }) =>
  (jsonLine(run.stderr) as { error?: { code?: string; message?: string } } | undefined)?.error;

for (const shell of shells) {
  describe(`macOS, under ${shell}`, () => {
    test("runs the app in /Applications with --cli and the arguments as they are", () => {
      const s = stage("Darwin");
      installMacApp(s, join(s.root, "Applications"), "<integer>1</integer>");
      const args = [
        "tasks",
        "add",
        "--title",
        "Write the “launch” post — it's $HOME; `rm` \\ \"quoted\"",
        "--notes",
        "two\nlines\tand a tab",
        "--start=2026-10-01T10:00",
        "",
        "- a dash",
        "*",
      ];

      const run = launch(args, s.env, shell);

      expect(run).toEqual({ code: 0, stdout: '{"ok":true}\n', stderr: "" });
      expect(calls(s.log)).toEqual([["--cli", ...args]]);
    });

    test("passes on the app's stdout, stderr and exit code", () => {
      const s = stage("Darwin");
      installMacApp(
        s,
        join(s.root, "Applications"),
        "<integer>1</integer>",
        `printf '{"error":{"code":"usage","message":"No command given."}}\\n' >&2; exit 2`,
      );

      const run = launch([], s.env, shell);

      expect(run.code).toBe(2);
      expect(run.stdout).toBe("");
      expect(error(run)).toEqual({ code: "usage", message: "No command given." });
      expect(calls(s.log)).toEqual([["--cli"]]);
    });

    test("finds the app in the user's own Applications folder", () => {
      const s = stage("Darwin");
      installMacApp(s, join(s.env.HOME, "Applications"), "<integer>1</integer>");

      expect(launch(["status"], s.env, shell).code).toBe(0);
      expect(calls(s.log)).toEqual([["--cli", "status"]]);
    });

    test("prefers /Applications to the user's folder", () => {
      const s = stage("Darwin");
      installMacApp(s, join(s.root, "Applications"), "<integer>1</integer>", "echo system");
      installMacApp(s, join(s.env.HOME, "Applications"), "<integer>1</integer>", "echo user");

      expect(launch(["status"], s.env, shell).stdout).toBe("system\n");
    });

    test("UNFOLD_APP names the app, wherever it is, even with spaces in its path", () => {
      const s = stage("Darwin");
      installMacApp(s, join(s.root, "Applications"), "<integer>1</integer>", "echo system");
      const app = installMacApp(s, join(s.root, "My Apps"), "<integer>1</integer>", "echo mine");

      const run = launch(["status"], { ...s.env, UNFOLD_APP: app }, shell);

      expect(run.stdout).toBe("mine\n");
    });

    test("asks Spotlight when the app is in neither folder", () => {
      const s = stage("Darwin");
      const app = installMacApp(s, join(s.root, "Elsewhere"), "<integer>1</integer>");
      writeExecutable(join(s.bin, "mdfind"), `#!/bin/sh\nprintf '%s\\n' "${app}" "/another/Unfold.app"\n`);

      expect(launch(["status"], s.env, shell).code).toBe(0);
      expect(calls(s.log)).toEqual([["--cli", "status"]]);
    });

    test("says so when Unfold isn't installed", () => {
      const s = stage("Darwin");
      writeExecutable(join(s.bin, "mdfind"), "#!/bin/sh\nexit 0\n");

      const run = launch(["status"], s.env, shell);

      expect(run.code).toBe(1);
      expect(run.stdout).toBe("");
      expect(error(run)?.code).toBe("notInstalled");
      expect(error(run)?.message).toContain("https://unfoldplanner.com");
    });

    test("says so when UNFOLD_APP names something that isn't the app", () => {
      const s = stage("Darwin");
      installMacApp(s, join(s.root, "Applications"), "<integer>1</integer>");

      const run = launch(["status"], { ...s.env, UNFOLD_APP: join(s.root, "Nothing.app") }, shell);

      expect(error(run)?.code).toBe("notInstalled");
      expect(calls(s.log)).toEqual([]);
    });

    test("never runs an app from before the command line: it would open its window", () => {
      const s = stage("Darwin");
      installMacApp(s, join(s.root, "Applications"));

      const run = launch(["tasks", "list"], s.env, shell);

      expect(run.code).toBe(1);
      expect(run.stdout).toBe("");
      expect(error(run)?.code).toBe("updateRequired");
      expect(calls(s.log)).toEqual([]);
    });

    test("doesn't take a contract that isn't a number for one", () => {
      const s = stage("Darwin");
      installMacApp(s, join(s.root, "Applications"), "<string>soon</string>");

      expect(error(launch(["status"], s.env, shell))?.code).toBe("updateRequired");
      expect(calls(s.log)).toEqual([]);
    });

    test("refuses an app whose command line is older than the skill's, and runs nothing", () => {
      const s = stage("Darwin");
      installMacApp(s, join(s.root, "Applications"), "<integer>0</integer>");

      const run = launch(["status"], s.env, shell);

      expect(run.code).toBe(1);
      expect(error(run)?.code).toBe("updateRequired");
      expect(calls(s.log)).toEqual([]);
    });

    test("refuses an app whose command line is newer than the skill's, and runs nothing", () => {
      const s = stage("Darwin");
      installMacApp(s, join(s.root, "Applications"), "<integer>2</integer>");

      const run = launch(["status"], s.env, shell);

      expect(run.code).toBe(1);
      expect(run.stdout).toBe("");
      expect(error(run)?.code).toBe("skillUpdateRequired");
      expect(calls(s.log)).toEqual([]);
    });
  });

  describe(`Linux, under ${shell}`, () => {
    /** A fake `unfold`: knows --cli with `contract`, or refuses it as the app did before its command line. */
    function installBinary(s: Stage, kind: "current" | "old", name = "unfold", contract = 1): string {
      const body =
        kind === "current"
          ? `if [ "$2" = version ]; then printf '{"app":{"platform":"linux"},"contract":${contract}}\\n'; else printf '{"ok":true}\\n'; fi`
          : "echo 'unfold: unknown option --cli' >&2; exit 1";
      return writeExecutable(join(s.bin, name), recorder(s.log, body));
    }

    const cache = (s: Stage) => join(s.env.HOME, ".cache/unfold-skill/contract");

    test("runs `unfold --cli` from the PATH with the arguments as they are", () => {
      const s = stage("Linux");
      installBinary(s, "current");
      const args = ["tasks", "add", "--title", "It's “done” — $HOME `x` \\", "", "*"];

      const run = launch(args, s.env, shell);

      expect(run).toEqual({ code: 0, stdout: '{"ok":true}\n', stderr: "" });
      // Once to ask which contract it follows, once for the command.
      expect(calls(s.log)).toEqual([
        ["--cli", "version"],
        ["--cli", ...args],
      ]);
    });

    test("asks the app for its contract once, until the app is replaced", () => {
      const s = stage("Linux");
      installBinary(s, "current");

      expect(launch(["status"], s.env, shell).code).toBe(0);
      expect(launch(["tasks", "list"], s.env, shell).code).toBe(0);
      expect(calls(s.log)).toEqual([
        ["--cli", "version"],
        ["--cli", "status"],
        ["--cli", "tasks", "list"],
      ]);
      expect(existsSync(cache(s))).toBe(true);

      // An update puts a new file in its place, as a package manager does, so the next command
      // asks again and finds the newer contract.
      installBinary(s, "current", "unfold.new", 2);
      renameSync(join(s.bin, "unfold.new"), join(s.bin, "unfold"));
      const run = launch(["status"], s.env, shell);

      expect(error(run)?.code).toBe("skillUpdateRequired");
      expect(calls(s.log).slice(3)).toEqual([["--cli", "version"]]);
    });

    test("XDG_CACHE_HOME is where the answer is kept", () => {
      const s = stage("Linux");
      installBinary(s, "current");
      const xdg = join(s.root, "xdg");

      expect(launch(["status"], { ...s.env, XDG_CACHE_HOME: xdg }, shell).code).toBe(0);

      expect(existsSync(join(xdg, "unfold-skill/contract"))).toBe(true);
      expect(existsSync(cache(s))).toBe(false);
    });

    test("runs the command even where the answer can't be kept", () => {
      const s = stage("Linux");
      installBinary(s, "current");
      const file = join(s.root, "not-a-folder");
      writeFileSync(file, "");

      const run = launch(["status"], { ...s.env, XDG_CACHE_HOME: file }, shell);

      expect(run).toEqual({ code: 0, stdout: '{"ok":true}\n', stderr: "" });
    });

    test("refuses an app whose command line is newer than the skill's, and runs nothing more", () => {
      const s = stage("Linux");
      installBinary(s, "current", "unfold", 2);

      const run = launch(["tasks", "list"], s.env, shell);

      expect(run.code).toBe(1);
      expect(run.stdout).toBe("");
      expect(error(run)?.code).toBe("skillUpdateRequired");
      expect(calls(s.log)).toEqual([["--cli", "version"]]);
    });

    test("UNFOLD_BIN names the binary", () => {
      const s = stage("Linux");
      const bin = installBinary(s, "current", "unfold-dev");

      const run = launch(["status"], { ...s.env, UNFOLD_BIN: bin }, shell);

      expect(run.code).toBe(0);
      expect(calls(s.log).at(-1)).toEqual(["--cli", "status"]);
    });

    test("says so when Unfold isn't installed", () => {
      const s = stage("Linux");

      const run = launch(["status"], s.env, shell);

      expect(run.code).toBe(1);
      expect(run.stdout).toBe("");
      expect(error(run)?.code).toBe("notInstalled");
    });

    test("says so when the app is from before its command line, and runs nothing more", () => {
      const s = stage("Linux");
      installBinary(s, "old");

      const run = launch(["tasks", "add", "--title", "x"], s.env, shell);

      expect(run.code).toBe(1);
      expect(run.stdout).toBe("");
      expect(error(run)?.code).toBe("updateRequired");
      // Only the question; the old app's own complaint isn't shown.
      expect(calls(s.log)).toEqual([["--cli", "version"]]);
      expect(run.stderr.split("\n").filter(Boolean)).toHaveLength(1);
    });
  });

  test(`another system is refused, under ${shell}`, () => {
    const s = stage("FreeBSD");

    const run = launch(["status"], s.env, shell);

    expect(run.code).toBe(1);
    expect(error(run)?.code).toBe("unsupported");
  });
}

test("without UNFOLD_SKILL_OS it asks the system which one this is", () => {
  const s = stage("unused");
  const { UNFOLD_SKILL_OS: _, ...env } = s.env;
  if (onMac) {
    installMacApp(s, join(s.root, "Applications"), "<integer>1</integer>");
  } else {
    writeExecutable(join(s.bin, "unfold"), recorder(s.log, 'printf \'{"contract":1}\\n\''));
  }

  expect(launch(["status"], env).code).toBe(0);
  expect(calls(s.log).at(-1)).toEqual(["--cli", "status"]);
});

test("every failure of its own is one line of JSON on stderr", () => {
  for (const os of ["Darwin", "Linux", "Plan9"]) {
    const s = stage(os);
    writeExecutable(join(s.bin, "mdfind"), "#!/bin/sh\nexit 0\n");
    const run = launch(["status"], s.env);
    const parsed = jsonLine(run.stderr) as { error: { code: string; message: string } };
    expect(Object.keys(parsed)).toEqual(["error"]);
    expect(Object.keys(parsed.error)).toEqual(["code", "message"]);
    expect(parsed.error.message.length).toBeGreaterThan(20);
  }
});
