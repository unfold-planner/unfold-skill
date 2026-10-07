# unfold-skill

The agent skill for Unfold and the contract of the command line it runs. `README.md` explains how
the pieces fit; `contract/README.md` is the contract. Workspace-wide docs are in `../docs/` (see
`../CLAUDE.md`).

## Commands

```sh
bun run check                         # done means this passes
bun test tests/launcher.test.ts       # one file
python3 contract/transcript.py        # rewrite contract/transcript.json after editing the steps
scripts/e2e-mac.sh                    # opens a stubbed Unfold window; run after changing how the app is told
```

## Rules

- **Contract first.** A change to what the command line does starts in `contract/README.md` and
  `contract/transcript.py`, then the Mac app, then the Linux client, then the skill (the README's
  "Changing the contract"). The clients' copies of `transcript.json` must stay byte-identical to
  this one; `bun run check` fails when they aren't.
- **Never edit `contract/transcript.json` by hand.** Edit `contract/transcript.py` and run it. Its
  expected values are written by hand from the contract, never recorded from a client: a step
  that fails in a client means the client is wrong, unless the contract and the transcript
  disagree with each other.
- **The skill never touches the database or a token.** Everything goes through the launcher and
  the app's `--cli`. Don't add a second way in.
- **The launcher is POSIX `sh`**, run as `sh scripts/unfold` (an install may drop its executable
  bit). No bashisms; the tests run it under `dash` too. It must never run a Mac app that lacks
  `UnfoldCLIContract`: that app would open its window. It runs only an app whose contract is the
  skill's (`contract=` in the launcher, `metadata.contract` in `SKILL.md`).
- **Keep `SKILL.md` short** and explain why, not just what; detail goes in
  `references/commands.md`. When behaviour changes, bump `metadata.version`.
- **Tests never use the user's data.** Fake apps for the launcher; `UNFOLD_HOME` or
  `UNFOLD_DATABASE` pointing at a throwaway folder for real binaries. A release build ignores
  both, so fail closed: give the process a throwaway `HOME` and XDG folders too, and check the
  build before a command that opens a database (`e2e-mac.sh` reads `UnfoldBuildConfiguration`).
- This public repo (`unfold-planner/unfold-skill`) is the sole source and install location. Do not
  copy the skill into another repo. Publishing is outward-facing: push and commit only when asked.
