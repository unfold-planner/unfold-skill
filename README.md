# unfold-skill

The agent skill for [Unfold](https://unfoldplanner.com), and the contract of the command line it
runs. With the skill installed, an agent (Claude Code, Codex, Cursor and others) can read and
change the user's tasks, projects and calendar time in the Unfold app on their computer.

```sh
npx skills add nemira-labs/skills --skill unfold
```

That's all a user does. There is nothing else to install and nothing to sign in to: the command
line is part of the app they already have.

## How it works

```text
agent ── skills/unfold/SKILL.md ── scripts/unfold ──▶ the app's own binary, `--cli`
                                                        │ the app's store code
                                                        ▼
                                          the local database (row + outbox entry)
                                                        │ tells the running app
                                                        ▼
                                  the app: reloads, and its sync sends the outbox (Premium)
```

- **One skill, one contract, a command line in each client.** The Mac app and the Linux client
  each build the same command line into their own binary, from their own store code, so trimming,
  limits, dates and outbox entries are the app's. The skill only knows the contract.
- **Free and Premium need no separate code.** Every write is saved with its outbox entry, as an
  edit in the app is, signed in or not. The app's sync sends the outbox only on a signed-in Premium
  account. Signed out or on Free, the change stays on the computer.
- **The command line never signs in and holds no token.** Syncing stays the app's job. After a
  write, the command line tells a running app, which reads the database again and syncs. With the
  app closed, the change waits for its next launch; `sync --open` starts it.
- **macOS:** the binary is sandboxed, and run with `--cli` it is the app in the app's own sandbox,
  so it reads the app's database with no extra permission. **Linux:** `unfold --cli`, before GTK
  starts.

## Layout

| Path | What |
|---|---|
| `skills/unfold/` | What gets installed: `SKILL.md`, the launcher `scripts/unfold`, and `references/commands.md`. |
| `contract/README.md` | The command line's contract, which both clients follow. |
| `contract/transcript.json` | The contract as a test: six scenes of steps both clients replay against their real store. Written by `contract/transcript.py`; never edit it by hand. |
| `contract/help.txt` | The `help` text, the same in both clients. |
| `tests/` | The launcher against fake apps; the contract's files against each other and the clients' copies; the clients' real binaries against the transcript. |
| `evals/evals.json` | Prompts to try the skill with an agent. |
| `scripts/` | `check.sh` (done means this passes), `e2e-mac.sh`, `publish.sh`. |

The command line itself is in the clients: `unfold/Unfold/CLI/` (Swift) and
`unfold-omarchy/crates/unfold-core/src/cli/` (Rust).

## Check

```sh
bun run check
```

It checks that `transcript.json` is what `transcript.py` writes, builds the Linux client's debug
binary when `../unfold-omarchy` is checked out, and runs the tests:

- `tests/launcher.test.ts`: finding the app, refusing one whose contract isn't the skill's (an app
  without a command line would open its window on the Mac instead of answering), asking the Linux
  app for its contract once until it's replaced, passing arguments, output and exit codes through
  unchanged, under `sh` and `dash`.
- `tests/contract.test.ts`: the transcript covers every command, error code and sync state; the
  skill and its reference name every command, option and code; the clients' copies of the
  transcript are this one byte for byte.
- `tests/conformance.test.ts`: the Linux client's real binary, through the launcher, replays the
  transcript's scenes that can be set up from outside (signed out, no app to tell), and its
  outbox is read back; the Mac app's Debug build, when there is one, answers the commands that
  open no database. Every run has a throwaway `HOME` and XDG folders as well as `UNFOLD_HOME`: a
  release build without the `debug-tools` feature ignores `UNFOLD_HOME`, and then fails the first
  test instead of writing to the user's data.

What needs an account or a running app is tested inside each client, where both can be set: the
whole transcript, and the app's real sync sending what the command line wrote
(`unfold/UnfoldTests/CLI/`, `unfold-omarchy/crates/unfold-core/tests/it/cli/`).

The two processes together, a running stubbed app and the command line on one throwaway database
until the app's sync has sent the change, are checked per platform:

- macOS: `scripts/e2e-mac.sh`, which opens a window. It also checks that `sync --open` starts the
  app and the app sends the change. An Unfold you have open is on another database, so it doesn't
  count and is left running. It runs nothing unless the app's `Info.plist` says
  `UnfoldBuildConfiguration` `Debug`: any other build would use the real database and account.
  Run it after changing how the command line reaches the app.
- Linux: `crates/unfold/tests/cli.rs` in `unfold-omarchy`, part of its `make linux-check` (a D-Bus
  session and Xvfb in Docker).

## Changing the contract

1. Change `contract/README.md`, then the steps in `contract/transcript.py`, and run
   `python3 contract/transcript.py`. Bump `contract` only for a change an older skill or app can't
   live with; adding a command or an option isn't one. The launcher runs only an app whose
   contract is the skill's (`contract=` in `skills/unfold/scripts/unfold`, and `metadata.contract`
   in `SKILL.md`), so a bump needs both apps and the skill released together.
2. Copy `contract/transcript.json` to `unfold/UnfoldTests/CLI/transcript.json` and make the Mac app
   pass it (`make quality` there).
3. Copy it to `unfold-omarchy/crates/unfold-core/tests/fixtures/cli-transcript.json` and make the
   Linux client pass it.
4. Update `skills/unfold/` to match, bump `metadata.version` in `SKILL.md`, and run
   `bun run check`.

## Evals

`evals/evals.json` has prompts a user would type. To try them, give an agent the skill folder and
a throwaway database, never the user's own:

- Linux client (runs on macOS too): a debug build with `UNFOLD_HOME=<empty folder>`,
  `UNFOLD_SKILL_OS=Linux` and `UNFOLD_BIN=<../unfold-omarchy/target/debug/unfold>`.
- Mac app: a Debug build with `UNFOLD_APP=<Unfold.app>`, `UNFOLD_AUTH_STUB=signedOut` and
  `UNFOLD_DATABASE=<a path in the app's container tmp folder>`.

## Publishing

The public [nemira-labs/skills](https://github.com/nemira-labs/skills) is what `npx skills add`
installs from; this repo is the source.

```sh
scripts/publish.sh <checkout of nemira-labs/skills>
```

It runs the check, copies `skills/unfold/` into the checkout and stops. Review the diff, add
`unfold` to that repo's README table, then commit and push there. Publish only once both apps
with the command line are released: on an older app the skill answers `updateRequired`.
