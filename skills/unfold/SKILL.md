---
name: unfold
description: >-
  Manage the user's tasks, projects and calendar time in Unfold, their to-do list and
  time-blocking calendar app for macOS and Omarchy (Linux). Use this whenever the user mentions
  Unfold, or asks to add, list, find, rename, schedule, reschedule, time-block, estimate,
  complete or delete their tasks or to-dos, to plan their day or week, to reserve time for work,
  to set a deadline, or to see what they have planned, even when they don't name the app. It
  works on the Unfold app installed on this computer, with no account needed; on a signed-in
  Premium account the changes also sync to the user's other devices.
compatibility: Requires the Unfold app on this computer (macOS 14 or later, or Omarchy on Arch Linux).
metadata:
  version: "0.1.1"
  author: "Unfold"
  # The command-line contract this skill speaks; the app says which one it follows.
  contract: "1"
  requires:
    bins: ["sh"]
    os: ["darwin", "linux"]
---

# Unfold

Unfold is a to-do list and a calendar in one app: a task gets a place in the week (a session), and
the user works on it then. This skill lets you read and change the user's tasks, projects and
sessions by running the app's own command line.

The command line is part of the installed app. It edits the same local database the app shows, by
the app's own rules, so what you change appears in the app. It needs no sign-in and makes no
network calls. If the user is signed in on Premium, the app sends your changes to their account as
it sends their own.

## Running a command

Run the launcher in this skill's folder with `sh`:

```sh
sh <this skill's folder>/scripts/unfold <command> [options]
```

- A command that works prints one JSON object on stdout and exits 0.
- One that fails prints `{"error":{"code":"…","message":"…"}}` on stderr and exits non-zero. The
  message says what to fix; read it before trying again.
- Quote every value (`--title "Write launch post"`).

Everything goes through this launcher. Don't open the app's database file or look for its
sign-in: the database's format is the app's own, a direct edit would skip the entry that makes a
change sync, and the app reads only what its command line saved.

## Start with `status`

Run `status` first in a conversation. It tells you what you're working with:

```json
{"contract":1,"app":{"platform":"macos","version":"0.1.0","running":true},
 "account":{"email":"ada@example.com","plan":"premium"},
 "sync":{"state":"syncing","reason":null,"pendingChanges":0},
 "timeZone":"Europe/Warsaw","now":"2026-10-01T09:40:00+02:00"}
```

Use `now` and `timeZone` for "today", "tomorrow" and "this week": they are the user's clock, which
may not be yours. `account` is `null` when nobody is signed in.

`sync` says where your changes go. Every change you make returns it too:

| `state` | `reason` | What it means |
|---|---|---|
| `local` | `signedOut` | Saved on this computer only. Nobody is signed in, which is fine: Unfold works without an account. Nothing reaches other devices. |
| `local` | `free` | Saved on this computer only. Syncing to other devices is part of Premium. |
| `local` | `otherAccount` | Saved on this computer only. Unfold is signed in to a different account than this data belongs to and is asking the user what to do; they need to answer in the app. |
| `syncing` | | Saved, and Unfold is sending it to their account now, so it reaches their other devices. |
| `pending` | `appNotRunning` | Saved. It reaches their other devices when Unfold next opens. |

`pendingChanges` counts changes the user's account hasn't received. While the state is `local` it
only grows, and that is normal: the changes are saved and nothing is stuck. It matters when the
state is `pending`.

Say where a change went only when it matters: when the user asks about sync or other devices, or
the state is `pending` or `otherAccount`. A user who isn't signed in doesn't need to hear about
accounts after every task.

When you finish a batch of changes and the state is `pending`, Unfold has to run to send them. How
it starts depends on `app.platform` in `status`:

- `macos`: run `sync --open` once. It starts Unfold in the background, without a window, so the
  changes go out; tell the user you did.
- `linux`: `sync --open` opens Unfold's window on the user's screen, so ask before running it.
  Otherwise tell them the changes go out when they next open Unfold.

Signing in, and buying
Premium, happen in the app; you can't do either from here, so point the user to the app if they
want their tasks on other devices.

## Commands

| Command | What it does |
|---|---|
| `status` | The account, where changes go, the time zone and the time. |
| `tasks list` | Open tasks, newest first. `--status open\|completed\|all`; `--from` and `--to` (a time or a day) keep tasks with a session or a deadline in that range; `--unscheduled` keeps tasks with no session at all (a date-only session is a session); `--project <id>\|none`; `--search <text>`. |
| `tasks show <id>` | One task. |
| `tasks add --title <text>` | A new task. `--notes`, `--project <id>`, `--estimate <minutes>`, and one of `--start <time> [--end <time>]`, `--day <day>`, `--deadline <time\|day>`. |
| `tasks update <id>` | `--title`, `--notes` (blank clears), `--project <id>\|none`, `--estimate <minutes>\|none`, `--deadline <time\|day>\|none`. |
| `tasks schedule <id>` | Puts the task on the calendar: `--start <time> [--end <time>]`, or `--day <day>` for a day without a time. |
| `tasks unschedule <id>` | Takes it off the calendar. |
| `tasks complete <id>`, `tasks reopen <id>` | |
| `tasks delete <id>` | Deletes it for good. |
| `projects list` | Projects, with how many open tasks each has. |
| `projects add --name <text>` | A new project. `--color blue\|green\|orange\|purple\|pink\|teal\|yellow\|gray` or `#rrggbb`. |
| `sync` | Tells a running Unfold to sync now; `--open` starts it first when needed (see above). |

`references/commands.md` has every option, the exact output of each command and the error codes.
Read it when a command fails in a way you don't understand, or before doing something the table
doesn't cover.

## Times

- Write a time as the user would say it, in their time zone, without an offset:
  `2026-10-01T10:00`. The command line reads it on the user's clock, clock changes included, so
  you don't work out offsets. Use `Z` or `+02:00` only for a time that was given to you that way.
- A day is `2026-10-01`.
- In `tasks list`, a day given to `--to` is included whole: `--from 2026-10-01 --to 2026-10-02` is
  both days, and the same day twice is that one day. A time given to `--to` is where the range
  stops.
- A deadline on a day (`--deadline 2026-10-09`) is the end of that day, and comes back as
  `…T23:59:59`. Say "due Friday", not "due 23:59".
- Times come back with the offset in force (`2026-10-01T10:00:00+02:00`).
- When the user's words leave the day or time open ("end of next week", "sometime in the
  afternoon"), pick the likely reading and say which one you picked, so they can correct it.

## How tasks hold time

A task's time is in two fields of its JSON:

- `sessions`: when the user plans to work on it. It is a list with one entry or none today. A
  timed session has a `start` and an `end`; a date-only one (`allDay: true`) names its days.
- `deadline`: when it must be done. A task has a session or a deadline, not both, so scheduling a
  task replaces its deadline. If the user wants both kept, say so rather than dropping the
  deadline silently: put it in the notes, or ask.

`estimateMinutes` is how long the user thinks it takes. A session started without an end runs for
the estimate, or 30 minutes when there is none. Give an `--end` when you know it.

## Working well

**Look before you change.** Ids are long and opaque; take them from `tasks list` or
`tasks show`, never from memory of an earlier conversation. To find a task the user names, list
with `--search`, and if several match, ask which.

**Find free time from the calendar you can see.** Before placing sessions, list the range
(`tasks list --from 2026-10-05 --to 2026-10-09` for that Monday to Friday) and keep new sessions clear of the ones there.
You see only Unfold's tasks. The user's meetings and other calendar events are not visible here
yet, so for anything but an obviously empty evening, ask what times are taken or propose times and
let the user correct them. Don't present a plan as conflict-free when you can't see their
meetings.

**Propose, then apply.** For one clear request ("add milk to my list", "move the demo to 3"), just
do it and say what you did. For a plan that touches several tasks (planning a week, breaking a
project into tasks and scheduling them), show the plan first, as a short list of task, day and
time, and apply it once the user agrees. They'll be looking at it in their calendar for days; a
moment to adjust it is worth more than speed.

**Ask before deleting.** `tasks delete` can't be undone from here. Confirm unless the user named
the task and asked for it to go ("delete", "remove", "get rid of") and exactly one task matches.
When they say a task is done, complete it; don't delete it.

**Report what changed.** After changes, say what is now different in plain words ("Moved 'Record
demo' to Friday 9:00-10:00"), not the JSON.

## When it doesn't run

| Error code | What happened | What to do |
|---|---|---|
| `notInstalled` | Unfold isn't on this computer. | Tell the user to get it at https://unfoldplanner.com. |
| `updateRequired` | Their Unfold is too old for this skill. | Ask them to update Unfold. |
| `skillUpdateRequired` | Their Unfold is newer than this skill. | Ask them to update this skill. |
| `unsupported` | This isn't macOS or Linux. | Unfold doesn't run here. |
| `usage` | The command was written wrong. | Fix it from the message; `references/commands.md` has the options. |
| `invalid` | A value the app wouldn't save (a blank title, an end before the start, a time it can't read). | Fix the value. |
| `notFound` | No task or project with that id. | List again; it may have been deleted. |
| `database` | The database couldn't be used. | Try once more; if it persists, tell the user and stop. |
| `appUnavailable` | `sync --open` couldn't start Unfold. | Ask the user to open Unfold. |
