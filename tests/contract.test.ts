// The contract's files agree with each other, with the skill, and with the copies the clients test
// against.
import { describe, expect, test } from "bun:test";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { repo, workspace } from "./support";

const read = (path: string) => readFileSync(join(repo, path), "utf8");
const transcript = JSON.parse(read("contract/transcript.json"));
const help = read("contract/help.txt");
const skill = read("skills/unfold/SKILL.md");
const reference = read("skills/unfold/references/commands.md");
const contract = read("contract/README.md");

/** The commands `help.txt` lists: the unindented-by-two lines that start a command. */
const commands = help
  .split("\n")
  .map((line) => /^ {2}([a-z]+(?: [a-z]+)?)(?= {2,}|$| <)/.exec(line)?.[1])
  .filter((command): command is string => command !== undefined);

const steps: { args: string[]; stdout: unknown; stderr: any; exit: number }[] = transcript.scenes.flatMap(
  (scene: { steps: unknown[] }) => scene.steps,
);

test("help lists the commands", () => {
  expect(commands).toEqual([
    "status",
    "version",
    "tasks list",
    "tasks show",
    "tasks add",
    "tasks update",
    "tasks schedule",
    "tasks unschedule",
    "tasks complete",
    "tasks reopen",
    "tasks delete",
    "projects list",
    "projects add",
    "sync",
  ]);
});

test("transcript.json is what transcript.py writes", () => {
  const check = spawnSync("python3", [join(repo, "contract/transcript.py"), "--check"], {
    encoding: "utf8",
  });
  expect(check.stderr).toBe("");
  expect(check.status).toBe(0);
});

describe("the transcript", () => {
  test("runs every command, and help", () => {
    const run = new Set(steps.map((step) => step.args.slice(0, 2).join(" ")));
    for (const command of [...commands, "help"]) {
      const used = [...run].some((args) => args === command || args.startsWith(`${command} `) || args.split(" ")[0] === command);
      expect({ command, used }).toEqual({ command, used: true });
    }
  });

  test("shows every error code the command line has, and every sync state", () => {
    const codes = new Set(steps.map((step) => step.stderr?.error?.code).filter(Boolean));
    const text = JSON.stringify(transcript);
    expect([...codes].sort()).toEqual(["appUnavailable", "invalid", "notFound", "readOnly", "usage"]);
    for (const state of ['"state": "local"', '"state": "syncing"', '"state": "pending"']) {
      expect(read("contract/transcript.json")).toContain(state);
    }
    for (const reason of ["signedOut", "free", "otherAccount", "appNotRunning"]) {
      expect(text).toContain(`"reason":"${reason}"`);
    }
  });

  test("a failing step has no stdout and the exit code its error asks for", () => {
    for (const step of steps.filter((step) => step.stderr !== null)) {
      expect(step.stdout).toBeNull();
      expect(step.exit).toBe(step.stderr.error.code === "usage" ? 2 : 1);
    }
  });

  test("its help is help.txt", () => {
    const step = steps.find((step) => step.args[0] === "help");
    expect(`${step?.stdout}\n`).toBe(help);
  });
});

describe("the clients' copies", () => {
  // Each client replays its own copy; a copy that drifted would let the clients drift.
  const copies = [
    ["unfold", "UnfoldTests/CLI/transcript.json"],
    ["unfold-omarchy", "crates/unfold-core/tests/fixtures/cli-transcript.json"],
  ];
  for (const [client, path] of copies) {
    const checkout = join(workspace, client);
    test.skipIf(!existsSync(checkout))(`${client}'s transcript is this one, byte for byte`, () => {
      expect(existsSync(join(checkout, path))).toBe(true);
      expect(readFileSync(join(checkout, path), "utf8")).toBe(read("contract/transcript.json"));
    });
  }
});

describe("the skill", () => {
  const frontmatter = /^---\n([\s\S]*?)\n---\n/.exec(skill)?.[1] ?? "";

  test("has the frontmatter agents read", () => {
    expect(frontmatter).toMatch(/^name: unfold$/m);
    const description = /^description: >-\n((?: {2}.*\n?)+)/m.exec(frontmatter)?.[1] ?? "";
    const text = description.replace(/\s+/g, " ").trim();
    expect(text.length).toBeGreaterThan(200);
    expect(text.length).toBeLessThanOrEqual(1024);
    expect(frontmatter).toMatch(/^ {2}version: "\d+\.\d+\.\d+"$/m);
    expect(frontmatter).toContain(`contract: "${transcript.contract}"`);
  });

  test("its launcher asks the app for the contract the skill speaks", () => {
    expect(read("skills/unfold/scripts/unfold")).toMatch(new RegExp(`^contract=${transcript.contract}$`, "m"));
  });

  test("stays short enough to be read whole", () => {
    expect(skill.split("\n").length).toBeLessThan(500);
  });

  test("names every command, in the skill and in its reference", () => {
    for (const command of commands) {
      // `status` says all `version` does; the skill leaves `version` to the reference.
      const inSkill = command === "version" || skill.includes(`\`${command}`);
      expect({ command, inSkill }).toEqual({ command, inSkill: true });
      expect({ command, inReference: reference.includes(`\`${command}`) }).toEqual({
        command,
        inReference: true,
      });
    }
  });

  test("names every option the contract has, in its reference", () => {
    const options = new Set(contract.match(/--[a-z]+/g));
    options.delete("--cli");
    options.delete("--name"); // also the contract's word for any option
    options.delete("--option");
    expect(options.size).toBeGreaterThan(12);
    for (const option of options) {
      expect({ option, inReference: reference.includes(option) }).toEqual({
        option,
        inReference: true,
      });
    }
    expect(reference).toContain("--name <text>");
  });

  test("explains every error code and sync state", () => {
    const codes = [
      "usage",
      "invalid",
      "notFound",
      "database",
      "appUnavailable",
      "readOnly",
      "notInstalled",
      "updateRequired",
      "skillUpdateRequired",
      "unsupported",
    ];
    for (const code of codes) {
      expect({ code, inSkill: skill.includes(`\`${code}\``) }).toEqual({ code, inSkill: true });
      expect({ code, inReference: reference.includes(`\`${code}\``) }).toEqual({
        code,
        inReference: true,
      });
    }
    for (const word of ["signedOut", "free", "otherAccount", "appNotRunning", "local", "syncing", "pending"]) {
      expect({ word, inSkill: skill.includes(`\`${word}\``) }).toEqual({ word, inSkill: true });
    }
  });

  test("points at files that are there", () => {
    expect(skill).toContain("scripts/unfold");
    expect(skill).toContain("references/commands.md");
    // Installed by copying: the launcher must stay runnable with `sh` whatever its mode.
    expect(statSync(join(repo, "skills/unfold/scripts/unfold")).isFile()).toBe(true);
    expect(read("skills/unfold/scripts/unfold").startsWith("#!/bin/sh\n")).toBe(true);
  });
});
