# The Unfold command line for agents, contract 1

Both clients ship the same command line inside the app, and the skill calls it. This file is the
contract: a client that follows it works with the skill unchanged. `transcript.json` is the same
contract as a test both clients replay (see "The transcript" at the end).

- macOS: `/Applications/Unfold.app/Contents/MacOS/Unfold --cli <command>` (the app's own binary, so it
  runs in the app's sandbox and reads the app's database).
- Linux: `unfold --cli <command>` (the app's own binary, before GTK starts).

The skill's launcher, `skills/unfold/scripts/unfold`, finds the right one.

## What it does and doesn't do

- It reads and writes the app's local database through the app's own store code. Every write is saved
  with its outbox entry in one transaction, exactly as an edit in the app is.
- It never signs in, never reads a token and never calls the backend. Syncing stays the app's job: on
  a signed-in Premium account the app sends the outbox, as it does for its own edits.
- After a write, it tells a running app to read the database again and sync.
- It holds no state of its own.

## Calling it

```text
unfold --cli <command> [<subcommand>] [<id>] [--option <value>]...
```

- An option is `--name value` or `--name=value`, in any order. One that takes a value takes the next
  argument as it is, whatever it starts with. `--unscheduled` and `--open` take no value.
- The command is read first (its words, then its options left to right, then its id), so a command
  that can't be read is `usage` before anything is looked up.
- A command that fails changes nothing, and takes no id from the ones a create would use.
- A write reads what it decides from, saves the change and reads what its answer shows in one
  transaction. An edit the app makes at the same time comes before it or after it, never in
  between, and once the change is saved the command doesn't fail.

### Output

- Success: exit code 0, and one JSON object on one line on stdout. `help` prints text instead.
- Failure: nothing on stdout, and `{"error":{"code":"…","message":"…"}}` on one line on stderr.

| Code | Exit | Meaning |
|---|---|---|
| `usage` | 2 | Unknown command or option, a missing value or id, an option given twice, options that exclude each other, nothing to change. |
| `invalid` | 1 | A value the app wouldn't save: a blank title, an end that isn't after the start, a time that can't be read, an estimate out of range, an unknown color. |
| `notFound` | 1 | No task or project with that id. |
| `database` | 1 | The database can't be opened, read or written. |
| `appUnavailable` | 1 | `sync --open` couldn't start the app. |

Every key is always present; a missing value is `null`.

## Times

**Read** (options):

| Form | Meaning |
|---|---|
| `2026-10-01T10:00`, `2026-10-01T10:00:00` | That wall-clock time in the computer's time zone. |
| `2026-10-01T10:00:00Z`, `2026-10-01T12:00:00+02:00` | That instant. Fractions of a second are allowed and kept to the millisecond. |
| `2026-10-01` | A day, where the option allows one (below). |

- A local time the clocks skip (spring) is read as the time that much later: `02:30` on a day the
  clocks jump from 02:00 to 03:00 is `03:30`. A local time that happens twice (autumn) is the first.
- A day runs from its first moment to the next day's first moment, and its last second is
  `23:59:59`, also where the clocks skip midnight and the day starts at `01:00`.
- `--from` takes a day as the midnight that starts it, and `--to` as the midnight that ends it, so
  `--from 2026-10-05 --to 2026-10-09` is those five days whole and `--from` and `--to` the same day is
  that day. `--deadline` takes a day as its last second (`23:59:59`), as the app's date-only deadline
  is. `--day` takes only a day. `--start` and `--end` take only a time.

**Written** (output), always in the computer's time zone:

- A time is `2026-10-01T10:00:00+02:00`; milliseconds are added only when they aren't zero
  (`…T10:00:00.250+02:00`). UTC is `+00:00`.
- A day is `2026-10-01`.

## Objects

### Task

```json
{
  "id": "0b8f6f0e-6c1b-4c35-9a53-0d6a1c2b7e11",
  "title": "Write launch post",
  "notes": null,
  "completed": false,
  "project": {"id": "…", "name": "Launch"},
  "estimateMinutes": 90,
  "sessions": [{"start": "2026-10-01T10:00:00+02:00", "end": "2026-10-01T11:30:00+02:00", "allDay": false}],
  "deadline": null,
  "createdAt": "2026-09-30T18:12:03+02:00"
}
```

- `project` is `null` for no project, and for a project id the database doesn't have.
- `sessions` is the task's time on the calendar, as the calendar draws it. The data holds one range per
  task today, so the list has one entry or none; it is a list so tasks with several sessions won't
  change the shape.
  - A timed session: `start`, `end` (times), `allDay: false`. A task with a start but no later end
    runs for its estimate, else 30 minutes.
  - A date-only session (a start at local midnight with no end, or an end at midnight or 23:59:59):
    `start`, `end` (days, the last day included), `allDay: true`.
- `deadline` is the end of a task that has no start; `null` otherwise. A task holds a session or a
  deadline, not both.

### Project

```json
{"id": "…", "name": "Launch", "color": "#4f8ef7", "openTasks": 3}
```

`openTasks` counts the project's tasks that aren't completed.

### Sync

Where a change goes. Part of `status`, `sync` and every write.

```json
{"state": "local", "reason": "signedOut", "pendingChanges": 3}
```

| `state` | `reason` | Meaning |
|---|---|---|
| `local` | `signedOut` | Nobody is signed in. The change stays on this computer. |
| `local` | `free` | Signed in on the Free plan. The change stays on this computer until the account is Premium. |
| `local` | `otherAccount` | Signed in to an account the data isn't linked to; the app is asking what to do. |
| `syncing` | `null` | The account syncs and the app is running: it was told, and sends the change within seconds. |
| `pending` | `appNotRunning` | The account syncs but the app isn't running: the change goes out when it next opens. |

The account syncs when the app's cached account is signed in, its plan includes sync, and the data is
linked to that account or to none yet. `pendingChanges` is how many changes the backend hasn't taken,
counted after this command's write.

## Commands

### `version`

```json
{"contract": 1, "app": {"platform": "macos", "version": "0.1.0"}}
```

Touches nothing. `platform` is `macos` or `linux`.

### `status`

```json
{
  "contract": 1,
  "app": {"platform": "macos", "version": "0.1.0", "running": true},
  "account": {"email": "ada@example.com", "plan": "premium"},
  "sync": {"state": "syncing", "reason": null, "pendingChanges": 0},
  "timeZone": "Europe/Warsaw",
  "now": "2026-10-01T09:40:00+02:00"
}
```

`account` is the app's cached sign-in (`plan` is `free` or `premium`), or `null` signed out. `now` is
cut to the whole second.

### `tasks list`

`{"tasks": [Task, …]}`, newest first (by creation time, then id, both descending), as the app lists them.

| Option | Keeps |
|---|---|
| `--status open\|completed\|all` | Open tasks by default. |
| `--from <time\|day>`, `--to <time\|day>` | Tasks with a session that overlaps `[from, to)`, or a deadline in it. A `--to` day is included whole (see "Times"); a `--to` time is not part of the range. Either may be left out. A task with neither a session nor a deadline never matches. |
| `--unscheduled` | Tasks with no session. |
| `--project <id>\|none` | Tasks in that project, or in none: `none` keeps every task shown with `project: null`, one whose project id the database doesn't have included. An unknown id is `notFound`. |
| `--search <text>` | Tasks whose title contains the text, ignoring case. |

Filters combine: a task must pass all of them.

### `tasks show <id>`

`{"task": Task}`.

### `tasks add`

`{"task": Task, "sync": Sync}`. The id is a new lowercase UUID v4 and `createdAt` is now.

| Option | |
|---|---|
| `--title <text>` | Required. Trimmed and cut to 500 UTF-16 units as the app does; blank is `invalid`. |
| `--notes <text>` | Trimmed and cut to 5000; blank means none. |
| `--project <id>` | Must exist. |
| `--estimate <minutes>` | A whole number from 1 to 10080. |
| `--start <time>` with optional `--end <time>` | A timed session. Without `--end`, it ends after the estimate, else after 30 minutes; the end is always saved. The end must be after the start. |
| `--day <day>` | A date-only session on that day: a start at its midnight and an end at its 23:59:59. |
| `--deadline <time\|day>` | A deadline and no session. |

`--day` excludes `--start` and `--end`; `--deadline` excludes all three; `--end` needs `--start`.

### `tasks update <id>`

`{"task": Task, "sync": Sync}`. At least one option; the rest of the task is kept.

| Option | |
|---|---|
| `--title <text>` | As in `add`. |
| `--notes <text>` | Blank clears the notes. |
| `--project <id>\|none` | `none` takes the task out of its project. |
| `--estimate <minutes>\|none` | `none` clears it. |
| `--deadline <time\|day>\|none` | Only for a task with no session: on one that has a session, a deadline is `invalid` (unschedule it first) and `none` changes nothing. |

Every option given goes into one outbox entry, those that match what the task already has included.
When none of them would change anything, nothing is written and the app isn't told; the answer is the
same.

### `tasks schedule <id>`

`{"task": Task, "sync": Sync}`. Sets the task's session, replacing the one it has and any deadline.
Takes `--start <time>` with optional `--end <time>` (without it, the task's estimate, else 30 minutes), or
`--day <day>`, as in `add`. Both ends are always sent together.

### `tasks unschedule <id>`

`{"task": Task, "sync": Sync}`. Removes the session. A task without one, a deadline included, is left
as it is.

### `tasks complete <id>`, `tasks reopen <id>`

`{"task": Task, "sync": Sync}`. A task already in that state is left as it is.

### `tasks delete <id>`

`{"deleted": {"id": "…", "title": "…"}, "sync": Sync}`.

### `projects list`

`{"projects": [Project, …]}` in the sidebar's order.

### `projects add`

`{"project": Project, "sync": Sync}`. The project goes after the others.

| Option | |
|---|---|
| `--name <text>` | Required. Trimmed and cut to 100 UTF-16 units; blank is `invalid`. |
| `--color <name\|#rrggbb>` | `blue` `#4f8ef7`, `green` `#3fb86a`, `orange` `#e8893a`, `purple` `#9b7bf0`, `pink` `#e0609b`, `teal` `#2fb3b0`, `yellow` `#d9b43a`, `gray` `#8a8d96`, or any `#rrggbb` (saved lowercase). Without it, the first of those no project uses yet; once all are used, they repeat in order by the number of projects. |

### `sync`

`{"sync": Sync, "opened": false}`. Tells a running app to sync now. With `--open`, starts the app when
the account syncs and the app isn't running (`opened: true`, and the state becomes `syncing`); on macOS it
opens without coming to the front. It never opens the app for an account that doesn't sync.

### `help`

Usage as plain text: `help.txt`, the same in both clients.

## Telling the app

After a write that changed something, the command line tells the app when it's running, whether or not
the account syncs, so the app shows the change. `sync` tells it only when the state is `syncing`: there
is nothing to show, and an account that doesn't sync has nothing to send. The app then reads the
database again and asks its sync for a run, as after one of its own edits. Each command asks once
whether the app is running, so its answer and what it told the app agree.

- macOS: the distributed notification `com.unfoldplanner.mac.localDataChanged`.
- Linux: the application action `agent-changed` of `dev.unfold.Unfold`, over D-Bus.

## The transcript

`transcript.json` lists scenes; each starts with an empty database and runs its steps in order. Each
client replays it inside its own tests against the real store, with the clock, the ids, the account and
the app's presence given by the step, and compares everything.

```json
{
  "name": "what the step shows",
  "given": {
    "now": "2026-10-01T07:40:00Z",
    "account": {"userId": "user_a", "email": "ada@example.com", "plan": "premium"},
    "linked": {"userId": "user_b", "email": "bob@example.com"},
    "appRunning": true,
    "canOpen": true,
    "ids": ["…"]
  },
  "args": ["tasks", "add", "--title", "Write launch post"],
  "exit": 0,
  "stdout": {},
  "stderr": null,
  "queued": [{"kind": "createTodo", "id": "…", "body": {}}],
  "notified": 1,
  "opened": 0
}
```

- `given` is optional and its keys stay in force for the rest of the scene: the clock, the cached
  account (`null` signs out), whether the app runs, whether it can be started. `ids` are added to the
  ids the next creates use, in order. `linked` links the database to that account, once.
- The scene's time zone is the file's `timeZone`, and the app version its `appVersion`. `$PLATFORM` in
  an expected value stands for the client's platform.
- `stdout` is the parsed JSON, or a string for `help`. `stderr` is the parsed error, or `null`.
- `queued` is what the step added to the outbox, in order: the change's kind, the id it's about, and
  the body the app will send the backend (`null` for a delete). Left out, it means nothing was added.
- `notified` and `opened` count how often the step told the app and started it; left out, zero.

The copies in `unfold/UnfoldTests/CLI/transcript.json` and
`unfold-omarchy/crates/unfold-core/tests/fixtures/cli-transcript.json` must be this file, byte for byte;
`bun run check` here fails when they aren't.
