# Unfold command reference

Every command is run through the launcher: `sh <skill folder>/scripts/unfold <command> [options]`.

## Contents

- [Calling and output](#calling-and-output)
- [Times and days](#times-and-days)
- [What comes back](#what-comes-back): Task, Project, Sync
- [Commands](#commands): status, version, tasks, projects, sync, help
- [Errors](#errors)

## Calling and output

- An option is `--name value` or `--name=value`, in any order. An option that takes a value takes
  the next argument as it is, so a title may start with a dash: `--title "- buy milk"`.
- `--unscheduled` and `--open` take no value.
- A command that works prints one JSON object on one line on stdout and exits 0. Every key is
  always present; a missing value is `null`.
- A command that fails prints nothing on stdout, prints
  `{"error":{"code":"…","message":"…"}}` on stderr, exits 2 for `usage` and 1 otherwise, and
  changes nothing. A command whose change was saved doesn't fail, so trying again after a failure
  never makes a change twice.

## Times and days

| You write | It means |
|---|---|
| `2026-10-01T10:00` or `2026-10-01T10:00:00` | That time on the user's clock. |
| `2026-10-01T10:00:00Z`, `2026-10-01T12:00:00+02:00` | That instant. |
| `2026-10-01` | A day. |

- `--start` and `--end` take a time. `--day` takes a day. `--from`, `--to` and `--deadline` take
  either. A day is the midnight that starts it for `--from`, the midnight that ends it for `--to`
  (so the day is included whole), and its last second (23:59:59) for `--deadline`.
- A local time the clocks skip in spring is read as that much later (02:30 becomes 03:30); one
  that happens twice in autumn is the first.
- Output is always on the user's clock with the offset: `2026-10-01T10:00:00+02:00`.
  Milliseconds appear only when they aren't zero. A day is `2026-10-01`.

## What comes back

### Task

```json
{
  "id": "0b8f6f0e-6c1b-4c35-9a53-0d6a1c2b7e11",
  "title": "Write launch post",
  "notes": null,
  "completed": false,
  "project": {"id": "5d1c…", "name": "Launch"},
  "estimateMinutes": 90,
  "sessions": [{"start": "2026-10-01T10:00:00+02:00", "end": "2026-10-01T11:30:00+02:00", "allDay": false}],
  "deadline": null,
  "createdAt": "2026-09-30T18:12:03+02:00"
}
```

- `sessions`: the task's time on the calendar, one entry or none.
  - Timed: `start` and `end` are times, `allDay` is `false`. A task saved with a start but no
    later end shows the end the calendar draws: the estimate, else 30 minutes.
  - Date-only: `start` and `end` are days, the last day included, `allDay` is `true`.
- `deadline`: set only on a task with no session.
- `project`: `null` when the task is in none.

### Project

```json
{"id": "5d1c…", "name": "Launch", "color": "#4f8ef7", "openTasks": 3}
```

### Sync

```json
{"state": "local", "reason": "signedOut", "pendingChanges": 3}
```

| `state` | `reason` | Meaning |
|---|---|---|
| `local` | `signedOut` | Nobody is signed in. The change stays on this computer. |
| `local` | `free` | Signed in on the Free plan, which doesn't sync. |
| `local` | `otherAccount` | Signed in to an account this data isn't linked to; the app is asking the user what to do. |
| `syncing` | `null` | The account syncs and Unfold is running: it sends the change within seconds. |
| `pending` | `appNotRunning` | The account syncs but Unfold isn't running: the change goes out when it opens. |

`pendingChanges` counts the changes the user's account hasn't received yet. Signed out or on Free
they simply wait, and go out if the user later signs in on Premium.

## Commands

### `status`

```json
{"contract": 1,
 "app": {"platform": "macos", "version": "0.1.0", "running": true},
 "account": {"email": "ada@example.com", "plan": "premium"},
 "sync": {"state": "syncing", "reason": null, "pendingChanges": 0},
 "timeZone": "Europe/Warsaw",
 "now": "2026-10-01T09:40:00+02:00"}
```

`account` is `null` signed out; `plan` is `free` or `premium`. `platform` is `macos` or `linux`.

### `version`

`{"contract": 1, "app": {"platform": "macos", "version": "0.1.0"}}`

### `tasks list`

`{"tasks": [Task, …]}`, newest first.

| Option | Keeps |
|---|---|
| `--status open\|completed\|all` | Open tasks unless you say otherwise. |
| `--from <time\|day>`, `--to <time\|day>` | Tasks with a session overlapping the range, or a deadline in it. A `--to` day is included whole; a `--to` time is where the range stops. Either may be left out. Tasks with neither a session nor a deadline never match a range. |
| `--unscheduled` | Tasks with no session. |
| `--project <id>\|none` | Tasks in that project, or in no project (every task shown with `project: null`). |
| `--search <text>` | Tasks whose title contains the text, ignoring case. |

A task must pass every filter given.

```sh
unfold tasks list --from 2026-10-05 --to 2026-10-11      # Monday to Sunday: sessions and deadlines
unfold tasks list --from 2026-10-05 --to 2026-10-05      # that one day
unfold tasks list --unscheduled                           # what still needs a time
unfold tasks list --search "launch" --status all
```

### `tasks show <id>`

`{"task": Task}`

### `tasks add`

`{"task": Task, "sync": Sync}`

| Option | |
|---|---|
| `--title <text>` | Required. Trimmed; at most 500 characters are kept. |
| `--notes <text>` | At most 5000 characters are kept. |
| `--project <id>` | An id from `projects list`. |
| `--estimate <minutes>` | 1 to 10080. |
| `--start <time>` with optional `--end <time>` | A timed session. Without `--end` it runs for the estimate, else 30 minutes. The end must be after the start. |
| `--day <day>` | A date-only session on that day. |
| `--deadline <time\|day>` | A deadline, and no session. |

Use one of `--start`, `--day`, `--deadline`, or none for a task that isn't planned yet.

```sh
unfold tasks add --title "Write launch post" --estimate 90 --start 2026-10-01T10:00
unfold tasks add --title "Book dentist" --day 2026-10-05
unfold tasks add --title "Send launch email" --deadline 2026-10-09T17:00 --project 5d1c…
```

### `tasks update <id>`

`{"task": Task, "sync": Sync}`. Give at least one option; the rest of the task is kept.

| Option | |
|---|---|
| `--title <text>` | |
| `--notes <text>` | `--notes ""` clears the notes. Notes are replaced, not appended: to add to them, read the task first and send the whole text. |
| `--project <id>\|none` | |
| `--estimate <minutes>\|none` | |
| `--deadline <time\|day>\|none` | Only on a task with no session. On a task that has one, a deadline is refused (`invalid`): unschedule it first. |

### `tasks schedule <id>`

`{"task": Task, "sync": Sync}`. Sets the task's session, replacing the one it has and any
deadline. `--start <time>` with optional `--end <time>` (without it: the task's estimate, else 30
minutes), or `--day <day>`.

### `tasks unschedule <id>`

`{"task": Task, "sync": Sync}`. Removes the session. A deadline is kept.

### `tasks complete <id>`, `tasks reopen <id>`

`{"task": Task, "sync": Sync}`

### `tasks delete <id>`

`{"deleted": {"id": "…", "title": "…"}, "sync": Sync}`. Can't be undone from the command line.

### `projects list`

`{"projects": [Project, …]}` in the app's sidebar order.

### `projects add`

`{"project": Project, "sync": Sync}`

| Option | |
|---|---|
| `--name <text>` | Required. At most 100 characters are kept. |
| `--color <name\|#rrggbb>` | `blue`, `green`, `orange`, `purple`, `pink`, `teal`, `yellow`, `gray`, or any `#rrggbb`. Left out, the app picks the next unused one. |

Projects can't be renamed or deleted from the command line; the user does that in the app.

### `sync`

`{"sync": Sync, "opened": false}`

- Unfold running on an account that syncs: tells it to sync now.
- `--open`: when the account syncs and Unfold isn't running, starts it (in the background on
  macOS; on Linux its window opens). `opened` is then `true` and the state `syncing`.
- An account that doesn't sync (`local`) is never a reason to open the app.

### `help`

The command list as text.

## Errors

| Code | Exit | Meaning |
|---|---|---|
| `usage` | 2 | Unknown command or option, a missing value or id, an option given twice, options that exclude each other, an update with nothing to change. |
| `invalid` | 1 | A blank title or name, an end that isn't after the start, a time or day that can't be read, an estimate outside 1 to 10080, an unknown status or color, a deadline on a task with a session. |
| `notFound` | 1 | No task or project with that id. |
| `database` | 1 | The app's database couldn't be opened, read or written. |
| `appUnavailable` | 1 | `sync --open` couldn't start Unfold. |
| `readOnly` | 1 | A change while the user has turned off "Agents can make changes" in Unfold's Settings › AI Agents. Nothing was saved; reading still works. Only the user can turn it on, in the app. |
| `notInstalled` | 1 | From the launcher: Unfold isn't on this computer. |
| `updateRequired` | 1 | From the launcher: the installed Unfold has no command line yet, or an older one than this skill speaks. |
| `skillUpdateRequired` | 1 | From the launcher: the installed Unfold's command line is newer than this skill speaks. |
| `unsupported` | 1 | From the launcher: this system isn't macOS or Linux. |

If the app is installed somewhere unusual, set `UNFOLD_APP` (macOS, the path of `Unfold.app`) or
`UNFOLD_BIN` (Linux, the `unfold` binary) before running the launcher.
