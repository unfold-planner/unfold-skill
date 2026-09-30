#!/usr/bin/env python3
"""Writes transcript.json, the contract as a test both clients replay.

Every expected value here is written by hand from contract/README.md: the helpers only fill in
keys that are the same in every step. Nothing is computed from a client.

    python3 contract/transcript.py           write transcript.json
    python3 contract/transcript.py --check   fail when transcript.json is out of date
"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
HELP = (HERE / "help.txt").read_text().rstrip("\n")


def uuid(tail):
    return "00000000-0000-4000-8000-" + tail.rjust(12, "0")


T = {n: uuid(str(n)) for n in range(1, 10)}
P = {n: uuid("a" + str(n)) for n in range(1, 10)}

ADA = {"userId": "user_a", "email": "ada@example.com", "plan": "premium"}
ADA_FREE = {"userId": "user_a", "email": "ada@example.com", "plan": "free"}


def sync(state, reason, pending):
    return {"state": state, "reason": reason, "pendingChanges": pending}


def local(pending, reason="signedOut"):
    return sync("local", reason, pending)


def syncing(pending):
    return sync("syncing", None, pending)


def waiting(pending):
    return sync("pending", "appNotRunning", pending)


def timed(start, end):
    return {"start": start, "end": end, "allDay": False}


def days(start, end=None):
    return {"start": start, "end": end or start, "allDay": True}


def task(id, title, created="2026-10-01T09:40:00+02:00", **fields):
    value = {
        "id": id,
        "title": title,
        "notes": None,
        "completed": False,
        "project": None,
        "estimateMinutes": None,
        "sessions": [],
        "deadline": None,
        "createdAt": created,
    }
    assert set(fields) <= set(value), fields
    value.update(fields)
    return value


def project(id, name, color, open_tasks=0):
    return {"id": id, "name": name, "color": color, "openTasks": open_tasks}


def status(account, sync, running, now="2026-10-01T09:40:00+02:00"):
    return {
        "contract": 1,
        "app": {"platform": "$PLATFORM", "version": "0.1.0", "running": running},
        "account": account and {"email": account["email"], "plan": account["plan"]},
        "sync": sync,
        "timeZone": "Europe/Warsaw",
        "now": now,
    }


def ok(name, args, stdout, given=None, queued=None, notified=0, opened=0):
    step = {"name": name}
    if given:
        step["given"] = given
    step.update({"args": args, "exit": 0, "stdout": stdout, "stderr": None})
    if queued:
        step["queued"] = queued
    if notified:
        step["notified"] = notified
    if opened:
        step["opened"] = opened
    return step


def fails(name, args, code, message, given=None):
    step = {"name": name}
    if given:
        step["given"] = given
    step.update(
        {
            "args": args,
            "exit": 2 if code == "usage" else 1,
            "stdout": None,
            "stderr": {"error": {"code": code, "message": message}},
        }
    )
    return step


def created_todo(id, title, created="2026-10-01T07:40:00.000Z", **body):
    return {
        "kind": "createTodo",
        "id": id,
        "body": {"id": id, "title": title, **body, "createdAt": created},
    }


def updated_todo(id, **body):
    return {"kind": "updateTodo", "id": id, "body": body}


def created_project(id, name, color):
    return {"kind": "createProject", "id": id, "body": {"id": id, "name": name, "color": color}}


HINT = 'Run "unfold --cli help" for the commands.'


def bad_time(text):
    return (
        f'Can\'t read "{text}" as a time. Use 2026-10-01T10:00, or add Z or an offset like +02:00.'
    )


def bad_moment(text):
    return f'Can\'t read "{text}" as a time or a day. Use 2026-10-01T10:00 or 2026-10-01.'


def no_task(id):
    return f'No task with id "{id}".'


# --------------------------------------------------------------------------------------------
# Signed out: everything stays on this computer, and every edit is still queued for a later
# sign-in, as the app's own edits are.


def signed_out():
    launch = {"id": P[1], "name": "Launch"}
    t1 = task(
        T[1],
        "Write launch post",
        "2026-10-01T09:41:00+02:00",
        notes="Outline first",
        project=launch,
        estimateMinutes=90,
    )
    t2 = task(
        T[2],
        "Record demo",
        "2026-10-01T09:42:00+02:00",
        sessions=[timed("2026-10-02T09:00:00+02:00", "2026-10-02T10:00:00+02:00")],
    )
    t3 = task(
        T[3],
        "Pricing FAQ",
        "2026-10-01T09:43:00+02:00",
        estimateMinutes=75,
        sessions=[timed("2026-10-02T10:30:00+02:00", "2026-10-02T11:45:00+02:00")],
    )
    t4 = task(
        T[4],
        "Press list",
        "2026-10-01T09:44:00+02:00",
        sessions=[timed("2026-10-02T14:00:00+02:00", "2026-10-02T14:30:00+02:00")],
    )
    t5 = task(
        T[5],
        "Book dentist",
        "2026-10-01T09:45:00+02:00",
        project={"id": P[2], "name": "Personal"},
        sessions=[days("2026-10-05")],
    )
    t6 = task(
        T[6],
        "Send launch email",
        "2026-10-01T09:46:00+02:00",
        project=launch,
        deadline="2026-10-09T17:00:00+02:00",
    )
    t7 = task(
        T[7], "File taxes", "2026-10-01T09:47:00+02:00", deadline="2026-10-31T23:59:59+01:00"
    )
    return [
        ok(
            "version touches nothing",
            ["version"],
            {"contract": 1, "app": {"platform": "$PLATFORM", "version": "0.1.0"}},
            given={"now": "2026-10-01T07:40:00Z", "account": None, "appRunning": False},
        ),
        ok("status, signed out", ["status"], status(None, local(0), False)),
        ok("no tasks yet", ["tasks", "list"], {"tasks": []}),
        ok("no projects yet", ["projects", "list"], {"projects": []}),
        ok(
            "a project's name is trimmed, and it takes the first color",
            ["projects", "add", "--name", "  Launch  "],
            {"project": project(P[1], "Launch", "#4f8ef7"), "sync": local(1)},
            given={"ids": [P[1]]},
            queued=[created_project(P[1], "Launch", "#4f8ef7")],
        ),
        ok(
            "a color by name",
            ["projects", "add", "--name", "Personal", "--color", "green"],
            {"project": project(P[2], "Personal", "#3fb86a"), "sync": local(2)},
            given={"ids": [P[2]]},
            queued=[created_project(P[2], "Personal", "#3fb86a")],
        ),
        ok(
            "a color as #rrggbb is saved lowercase",
            ["projects", "add", "--name", "Learning", "--color", "#AABBCC"],
            {"project": project(P[3], "Learning", "#aabbcc"), "sync": local(3)},
            given={"ids": [P[3]]},
            queued=[created_project(P[3], "Learning", "#aabbcc")],
        ),
        ok(
            "without a color, the first one no project uses",
            ["projects", "add", "--name", "Health"],
            {"project": project(P[4], "Health", "#e8893a"), "sync": local(4)},
            given={"ids": [P[4]]},
            queued=[created_project(P[4], "Health", "#e8893a")],
        ),
        ok(
            "a task with notes, a project and an estimate, not on the calendar",
            [
                "tasks",
                "add",
                "--title",
                "Write launch post",
                "--project",
                P[1],
                "--estimate",
                "90",
                "--notes",
                "Outline first",
            ],
            {"task": t1, "sync": local(5)},
            given={"now": "2026-10-01T07:41:00Z", "ids": [T[1]]},
            queued=[
                created_todo(
                    T[1],
                    "Write launch post",
                    "2026-10-01T07:41:00.000Z",
                    description="Outline first",
                    projectId=P[1],
                    estimatedMinutes=90,
                )
            ],
        ),
        ok(
            "a session from local times",
            [
                "tasks",
                "add",
                "--title",
                "Record demo",
                "--start",
                "2026-10-02T09:00",
                "--end",
                "2026-10-02T10:00",
            ],
            {"task": t2, "sync": local(6)},
            given={"now": "2026-10-01T07:42:00Z", "ids": [T[2]]},
            queued=[
                created_todo(
                    T[2],
                    "Record demo",
                    "2026-10-01T07:42:00.000Z",
                    startsAt="2026-10-02T07:00:00.000Z",
                    endsAt="2026-10-02T08:00:00.000Z",
                )
            ],
        ),
        ok(
            "without an end, a session lasts the estimate, and the end is saved",
            [
                "tasks",
                "add",
                "--title",
                "Pricing FAQ",
                "--start",
                "2026-10-02T10:30:00+02:00",
                "--estimate",
                "75",
            ],
            {"task": t3, "sync": local(7)},
            given={"now": "2026-10-01T07:43:00Z", "ids": [T[3]]},
            queued=[
                created_todo(
                    T[3],
                    "Pricing FAQ",
                    "2026-10-01T07:43:00.000Z",
                    startsAt="2026-10-02T08:30:00.000Z",
                    endsAt="2026-10-02T09:45:00.000Z",
                    estimatedMinutes=75,
                )
            ],
        ),
        ok(
            "without an end or an estimate, 30 minutes; --name=value works too",
            ["tasks", "add", "--title=Press list", "--start=2026-10-02T12:00:00Z"],
            {"task": t4, "sync": local(8)},
            given={"now": "2026-10-01T07:44:00Z", "ids": [T[4]]},
            queued=[
                created_todo(
                    T[4],
                    "Press list",
                    "2026-10-01T07:44:00.000Z",
                    startsAt="2026-10-02T12:00:00.000Z",
                    endsAt="2026-10-02T12:30:00.000Z",
                )
            ],
        ),
        ok(
            "a date-only session runs from the day's midnight to its last second",
            ["tasks", "add", "--title", "Book dentist", "--day", "2026-10-05", "--project", P[2]],
            {"task": t5, "sync": local(9)},
            given={"now": "2026-10-01T07:45:00Z", "ids": [T[5]]},
            queued=[
                created_todo(
                    T[5],
                    "Book dentist",
                    "2026-10-01T07:45:00.000Z",
                    startsAt="2026-10-04T22:00:00.000Z",
                    endsAt="2026-10-05T21:59:59.000Z",
                    projectId=P[2],
                )
            ],
        ),
        ok(
            "a deadline is an end without a start",
            [
                "tasks",
                "add",
                "--title",
                "Send launch email",
                "--deadline",
                "2026-10-09T17:00",
                "--project",
                P[1],
            ],
            {"task": t6, "sync": local(10)},
            given={"now": "2026-10-01T07:46:00Z", "ids": [T[6]]},
            queued=[
                created_todo(
                    T[6],
                    "Send launch email",
                    "2026-10-01T07:46:00.000Z",
                    endsAt="2026-10-09T15:00:00.000Z",
                    projectId=P[1],
                )
            ],
        ),
        ok(
            "a deadline on a day is its last second, in that day's offset",
            ["tasks", "add", "--title", "File taxes", "--deadline", "2026-10-31"],
            {"task": t7, "sync": local(11)},
            given={"now": "2026-10-01T07:47:00Z", "ids": [T[7]]},
            queued=[
                created_todo(
                    T[7],
                    "File taxes",
                    "2026-10-01T07:47:00.000Z",
                    endsAt="2026-10-31T22:59:59.000Z",
                )
            ],
        ),
        ok("open tasks, newest first", ["tasks", "list"], {"tasks": [t7, t6, t5, t4, t3, t2, t1]}),
        ok(
            "one day, whole: --to a day runs to the day's end",
            ["tasks", "list", "--from", "2026-10-02", "--to", "2026-10-02"],
            {"tasks": [t4, t3, t2]},
        ),
        ok(
            "--to a time stops there",
            ["tasks", "list", "--from", "2026-10-02", "--to", "2026-10-02T14:00"],
            {"tasks": [t3, t2]},
        ),
        ok(
            "a range keeps date-only sessions and deadlines in it",
            ["tasks", "list", "--from", "2026-10-05T00:00", "--to", "2026-10-09"],
            {"tasks": [t6, t5]},
        ),
        ok(
            "a day's deadline, at its last second, is on that day",
            ["tasks", "list", "--from", "2026-10-31", "--to", "2026-10-31"],
            {"tasks": [t7]},
        ),
        ok(
            "the day before a date-only session ends before it",
            ["tasks", "list", "--from", "2026-10-03", "--to", "2026-10-04"],
            {"tasks": []},
        ),
        ok("tasks with no session", ["tasks", "list", "--unscheduled"], {"tasks": [t7, t6, t1]}),
        ok("a project's tasks", ["tasks", "list", "--project", P[1]], {"tasks": [t6, t1]}),
        ok(
            "tasks in no project",
            ["tasks", "list", "--project", "none"],
            {"tasks": [t7, t4, t3, t2]},
        ),
        ok(
            "a search ignores case",
            ["tasks", "list", "--search", "LAUNCH"],
            {"tasks": [t6, t1]},
        ),
        ok(
            "filters combine",
            [
                "tasks",
                "list",
                "--unscheduled",
                "--project",
                P[1],
                "--from",
                "2026-10-09",
                "--to",
                "2026-10-09",
            ],
            {"tasks": [t6]},
        ),
        ok("one task", ["tasks", "show", T[2]], {"task": t2}),
        ok(
            "projects in the sidebar's order, with their open tasks",
            ["projects", "list"],
            {
                "projects": [
                    project(P[1], "Launch", "#4f8ef7", 2),
                    project(P[2], "Personal", "#3fb86a", 1),
                    project(P[3], "Learning", "#aabbcc"),
                    project(P[4], "Health", "#e8893a"),
                ]
            },
        ),
        ok(
            "everything waits for a sign-in",
            ["status"],
            status(None, local(11), False, "2026-10-01T09:47:00+02:00"),
        ),
    ]


# --------------------------------------------------------------------------------------------
# Premium with Unfold running: each change is queued with the body the app will send, and the
# app is told, once per change.


def premium_running():
    t = T[1]
    launch = {"id": P[1], "name": "Launch"}
    base = dict(estimateMinutes=45)
    renamed = "Write the launch post"
    return [
        ok(
            "status, signed in on Premium with Unfold running",
            ["status"],
            status(ADA, syncing(0), True),
            given={"now": "2026-10-01T07:40:00Z", "account": ADA, "appRunning": True},
        ),
        ok(
            "a new project is sent, and the app told",
            ["projects", "add", "--name", "Launch"],
            {"project": project(P[1], "Launch", "#4f8ef7"), "sync": syncing(1)},
            given={"ids": [P[1]]},
            queued=[created_project(P[1], "Launch", "#4f8ef7")],
            notified=1,
        ),
        ok(
            "a new task",
            ["tasks", "add", "--title", "Write launch post", "--estimate", "90"],
            {"task": task(t, "Write launch post", estimateMinutes=90), "sync": syncing(2)},
            given={"ids": [t]},
            queued=[created_todo(t, "Write launch post", estimatedMinutes=90)],
            notified=1,
        ),
        ok(
            "several changes are one entry; notes are trimmed",
            [
                "tasks",
                "update",
                t,
                "--title",
                renamed,
                "--notes",
                "  Outline first.  ",
                "--project",
                P[1],
            ],
            {
                "task": task(
                    t, renamed, notes="Outline first.", project=launch, estimateMinutes=90
                ),
                "sync": syncing(3),
            },
            queued=[
                updated_todo(t, title=renamed, description="Outline first.", projectId=P[1])
            ],
            notified=1,
        ),
        ok(
            "blank notes and none clear",
            ["tasks", "update", t, "--notes", "", "--project", "none", "--estimate", "none"],
            {"task": task(t, renamed), "sync": syncing(4)},
            queued=[updated_todo(t, description=None, projectId=None, estimatedMinutes=None)],
            notified=1,
        ),
        ok(
            "an estimate",
            ["tasks", "update", t, "--estimate", "45"],
            {"task": task(t, renamed, **base), "sync": syncing(5)},
            queued=[updated_todo(t, estimatedMinutes=45)],
            notified=1,
        ),
        ok(
            "a change that changes nothing writes nothing and tells nobody",
            ["tasks", "update", t, "--estimate", "45"],
            {"task": task(t, renamed, **base), "sync": syncing(5)},
        ),
        ok(
            "scheduling without an end uses the task's estimate",
            ["tasks", "schedule", t, "--start", "2026-10-02T09:00"],
            {
                "task": task(
                    t,
                    renamed,
                    sessions=[timed("2026-10-02T09:00:00+02:00", "2026-10-02T09:45:00+02:00")],
                    **base,
                ),
                "sync": syncing(6),
            },
            queued=[
                updated_todo(
                    t, startsAt="2026-10-02T07:00:00.000Z", endsAt="2026-10-02T07:45:00.000Z"
                )
            ],
            notified=1,
        ),
        ok(
            "moving a session sends both ends",
            ["tasks", "schedule", t, "--start", "2026-10-02T13:00", "--end", "2026-10-02T15:30"],
            {
                "task": task(
                    t,
                    renamed,
                    sessions=[timed("2026-10-02T13:00:00+02:00", "2026-10-02T15:30:00+02:00")],
                    **base,
                ),
                "sync": syncing(7),
            },
            queued=[
                updated_todo(
                    t, startsAt="2026-10-02T11:00:00.000Z", endsAt="2026-10-02T13:30:00.000Z"
                )
            ],
            notified=1,
        ),
        fails(
            "a task with a session can't take a deadline",
            ["tasks", "update", t, "--deadline", "2026-10-09"],
            "invalid",
            "This task has time on the calendar, so it can't have a deadline. Unschedule it first.",
        ),
        ok(
            "and has none to clear",
            ["tasks", "update", t, "--deadline", "none"],
            {
                "task": task(
                    t,
                    renamed,
                    sessions=[timed("2026-10-02T13:00:00+02:00", "2026-10-02T15:30:00+02:00")],
                    **base,
                ),
                "sync": syncing(7),
            },
        ),
        ok(
            "a date-only session",
            ["tasks", "schedule", t, "--day", "2026-10-06"],
            {"task": task(t, renamed, sessions=[days("2026-10-06")], **base), "sync": syncing(8)},
            queued=[
                updated_todo(
                    t, startsAt="2026-10-05T22:00:00.000Z", endsAt="2026-10-06T21:59:59.000Z"
                )
            ],
            notified=1,
        ),
        ok(
            "unscheduling clears both ends",
            ["tasks", "unschedule", t],
            {"task": task(t, renamed, **base), "sync": syncing(9)},
            queued=[updated_todo(t, startsAt=None, endsAt=None)],
            notified=1,
        ),
        ok(
            "unscheduling a task with no session changes nothing",
            ["tasks", "unschedule", t],
            {"task": task(t, renamed, **base), "sync": syncing(9)},
        ),
        ok(
            "a deadline on a day",
            ["tasks", "update", t, "--deadline", "2026-10-09"],
            {
                "task": task(t, renamed, deadline="2026-10-09T23:59:59+02:00", **base),
                "sync": syncing(10),
            },
            queued=[updated_todo(t, endsAt="2026-10-09T21:59:59.000Z")],
            notified=1,
        ),
        ok(
            "unscheduling keeps a deadline",
            ["tasks", "unschedule", t],
            {
                "task": task(t, renamed, deadline="2026-10-09T23:59:59+02:00", **base),
                "sync": syncing(10),
            },
        ),
        ok(
            "clearing the deadline",
            ["tasks", "update", t, "--deadline", "none"],
            {"task": task(t, renamed, **base), "sync": syncing(11)},
            queued=[updated_todo(t, endsAt=None)],
            notified=1,
        ),
        ok(
            "a deadline at a time",
            ["tasks", "update", t, "--deadline", "2026-10-09T17:00"],
            {
                "task": task(t, renamed, deadline="2026-10-09T17:00:00+02:00", **base),
                "sync": syncing(12),
            },
            queued=[updated_todo(t, endsAt="2026-10-09T15:00:00.000Z")],
            notified=1,
        ),
        ok(
            "scheduling replaces the deadline",
            ["tasks", "schedule", t, "--start", "2026-10-08T10:00", "--end", "2026-10-08T11:00"],
            {
                "task": task(
                    t,
                    renamed,
                    sessions=[timed("2026-10-08T10:00:00+02:00", "2026-10-08T11:00:00+02:00")],
                    **base,
                ),
                "sync": syncing(13),
            },
            queued=[
                updated_todo(
                    t, startsAt="2026-10-08T08:00:00.000Z", endsAt="2026-10-08T09:00:00.000Z"
                )
            ],
            notified=1,
        ),
        ok(
            "completing",
            ["tasks", "complete", t],
            {
                "task": task(
                    t,
                    renamed,
                    completed=True,
                    sessions=[timed("2026-10-08T10:00:00+02:00", "2026-10-08T11:00:00+02:00")],
                    **base,
                ),
                "sync": syncing(14),
            },
            queued=[updated_todo(t, completed=True)],
            notified=1,
        ),
        ok(
            "completing a completed task changes nothing",
            ["tasks", "complete", t],
            {
                "task": task(
                    t,
                    renamed,
                    completed=True,
                    sessions=[timed("2026-10-08T10:00:00+02:00", "2026-10-08T11:00:00+02:00")],
                    **base,
                ),
                "sync": syncing(14),
            },
        ),
        ok("the list is of open tasks", ["tasks", "list"], {"tasks": []}),
        ok(
            "completed tasks on request",
            ["tasks", "list", "--status", "completed"],
            {
                "tasks": [
                    task(
                        t,
                        renamed,
                        completed=True,
                        sessions=[
                            timed("2026-10-08T10:00:00+02:00", "2026-10-08T11:00:00+02:00")
                        ],
                        **base,
                    )
                ]
            },
        ),
        ok(
            "reopening",
            ["tasks", "reopen", t],
            {
                "task": task(
                    t,
                    renamed,
                    sessions=[timed("2026-10-08T10:00:00+02:00", "2026-10-08T11:00:00+02:00")],
                    **base,
                ),
                "sync": syncing(15),
            },
            queued=[updated_todo(t, completed=False)],
            notified=1,
        ),
        ok(
            "the project's open tasks",
            ["projects", "list"],
            {"projects": [project(P[1], "Launch", "#4f8ef7")]},
        ),
        ok(
            "deleting",
            ["tasks", "delete", t],
            {"deleted": {"id": t, "title": renamed}, "sync": syncing(16)},
            queued=[{"kind": "deleteTodo", "id": t, "body": None}],
            notified=1,
        ),
        fails("a deleted task is gone", ["tasks", "show", t], "notFound", no_task(t)),
        fails("and can't be deleted twice", ["tasks", "delete", t], "notFound", no_task(t)),
        ok("every change is waiting for the app's sync", ["status"], status(ADA, syncing(16), True)),
    ]


# --------------------------------------------------------------------------------------------
# Where a change goes: the plan, the running app and the linked account decide.


def where_changes_go():
    return [
        ok(
            "on Free, signed in, changes stay here",
            ["status"],
            status(ADA_FREE, local(0, "free"), True),
            given={"now": "2026-10-01T07:40:00Z", "account": ADA_FREE, "appRunning": True},
        ),
        ok(
            "but a running app is still told, so it shows the change",
            ["tasks", "add", "--title", "Buy milk"],
            {"task": task(T[1], "Buy milk"), "sync": local(1, "free")},
            given={"ids": [T[1]]},
            queued=[created_todo(T[1], "Buy milk")],
            notified=1,
        ),
        ok(
            "sync does nothing for an account that doesn't sync",
            ["sync"],
            {"sync": local(1, "free"), "opened": False},
        ),
        ok(
            "and never opens the app for one",
            ["sync", "--open"],
            {"sync": local(1, "free"), "opened": False},
            given={"appRunning": False},
        ),
        ok(
            "on Premium with Unfold closed, changes wait for it",
            ["status"],
            status(ADA, waiting(1), False),
            given={"account": ADA},
        ),
        ok(
            "a change waits, and nobody is told",
            ["tasks", "add", "--title", "Call Ada"],
            {"task": task(T[2], "Call Ada"), "sync": waiting(2)},
            given={"ids": [T[2]]},
            queued=[created_todo(T[2], "Call Ada")],
        ),
        ok("sync alone doesn't open the app", ["sync"], {"sync": waiting(2), "opened": False}),
        fails(
            "sync --open says when the app can't be started",
            ["sync", "--open"],
            "appUnavailable",
            "Couldn't open Unfold. Open it yourself, then run sync again.",
            given={"canOpen": False},
        ),
        ok(
            "sync --open starts the app, which then syncs",
            ["sync", "--open"],
            {"sync": syncing(2), "opened": True},
            given={"canOpen": True},
            opened=1,
        ),
        ok(
            "sync tells a running app",
            ["sync"],
            {"sync": syncing(2), "opened": False},
            given={"appRunning": True},
            notified=1,
        ),
        ok(
            "sync --open doesn't open a running app",
            ["sync", "--open"],
            {"sync": syncing(2), "opened": False},
            notified=1,
        ),
        ok(
            "data linked to the account syncs",
            ["status"],
            status(ADA, syncing(2), True),
            given={"linked": {"userId": "user_a", "email": "ada@example.com"}},
        ),
        ok(
            "data linked to another account doesn't",
            ["status"],
            status(ADA, local(2, "otherAccount"), True),
            given={"linked": {"userId": "user_b", "email": "bob@example.com"}},
        ),
        ok(
            "a change then stays here",
            ["tasks", "add", "--title", "Stays here"],
            {"task": task(T[3], "Stays here"), "sync": local(3, "otherAccount")},
            given={"ids": [T[3]]},
            queued=[created_todo(T[3], "Stays here")],
            notified=1,
        ),
        ok(
            "signed out again",
            ["status"],
            status(None, local(3), False),
            given={"account": None, "appRunning": False},
        ),
    ]


# --------------------------------------------------------------------------------------------
# Times: read in the computer's time zone (Europe/Warsaw here) or as given, written with the
# offset in force at that moment.


def times():
    gap = task(
        T[1],
        "Gap",
        sessions=[timed("2027-03-28T03:30:00+02:00", "2027-03-28T04:00:00+02:00")],
    )
    twice = task(
        T[2],
        "Twice",
        sessions=[timed("2026-10-25T02:30:00+02:00", "2026-10-25T02:00:00+01:00")],
    )
    millis = task(
        T[3],
        "Millis",
        sessions=[timed("2026-10-02T11:00:00.250+02:00", "2026-10-02T11:30:00.123+02:00")],
    )
    west = task(
        T[4],
        "West",
        sessions=[timed("2026-10-02T16:00:00+02:00", "2026-10-02T16:30:00+02:00")],
    )
    midnight = task(
        T[5],
        "Midnight",
        sessions=[timed("2026-10-03T00:00:00+02:00", "2026-10-03T01:00:00+02:00")],
    )
    two_days = task(T[6], "Two days", sessions=[days("2026-10-03", "2026-10-04")])
    trimmed = task(T[7], "Trim me")
    add = ["tasks", "add", "--title"]
    return [
        ok(
            "a local time the clocks skip is that much later",
            add + ["Gap", "--start", "2027-03-28T02:30"],
            {"task": gap, "sync": local(1)},
            given={
                "now": "2026-10-01T07:40:00Z",
                "account": None,
                "appRunning": False,
                "ids": [T[n] for n in range(1, 8)],
            },
            queued=[
                created_todo(
                    T[1],
                    "Gap",
                    startsAt="2027-03-28T01:30:00.000Z",
                    endsAt="2027-03-28T02:00:00.000Z",
                )
            ],
        ),
        ok(
            "a local time that happens twice is the first; the end is in the new offset",
            add + ["Twice", "--start", "2026-10-25T02:30"],
            {"task": twice, "sync": local(2)},
            queued=[
                created_todo(
                    T[2],
                    "Twice",
                    startsAt="2026-10-25T00:30:00.000Z",
                    endsAt="2026-10-25T01:00:00.000Z",
                )
            ],
        ),
        ok(
            "milliseconds are kept, and further digits dropped",
            add
            + [
                "Millis",
                "--start",
                "2026-10-02T09:00:00.250Z",
                "--end",
                "2026-10-02T09:30:00.123456Z",
            ],
            {"task": millis, "sync": local(3)},
            queued=[
                created_todo(
                    T[3],
                    "Millis",
                    startsAt="2026-10-02T09:00:00.250Z",
                    endsAt="2026-10-02T09:30:00.123Z",
                )
            ],
        ),
        ok(
            "an offset west of UTC",
            add + ["West", "--start", "2026-10-02T09:00:00-05:00"],
            {"task": west, "sync": local(4)},
            queued=[
                created_todo(
                    T[4],
                    "West",
                    startsAt="2026-10-02T14:00:00.000Z",
                    endsAt="2026-10-02T14:30:00.000Z",
                )
            ],
        ),
        ok(
            "a session from midnight with a time for its end is timed",
            add + ["Midnight", "--start", "2026-10-03T00:00", "--end", "2026-10-03T01:00"],
            {"task": midnight, "sync": local(5)},
            queued=[
                created_todo(
                    T[5],
                    "Midnight",
                    startsAt="2026-10-02T22:00:00.000Z",
                    endsAt="2026-10-02T23:00:00.000Z",
                )
            ],
        ),
        ok(
            "from midnight to midnight is date-only, the last day included",
            add + ["Two days", "--start", "2026-10-03T00:00", "--end", "2026-10-05T00:00"],
            {"task": two_days, "sync": local(6)},
            queued=[
                created_todo(
                    T[6],
                    "Two days",
                    startsAt="2026-10-02T22:00:00.000Z",
                    endsAt="2026-10-04T22:00:00.000Z",
                )
            ],
        ),
        ok(
            "a range is [from, to): a session that ends at from or starts at to is out",
            [
                "tasks",
                "list",
                "--from",
                "2026-10-02T11:30:00.123+02:00",
                "--to",
                "2026-10-02T16:00:00+02:00",
            ],
            {"tasks": []},
        ),
        ok(
            "and one a moment inside is in",
            [
                "tasks",
                "list",
                "--from",
                "2026-10-02T11:30:00+02:00",
                "--to",
                "2026-10-02T16:00:01+02:00",
            ],
            {"tasks": [west, millis]},
        ),
        ok(
            "a range inside the repeated hour",
            [
                "tasks",
                "list",
                "--from",
                "2026-10-25T02:45:00+02:00",
                "--to",
                "2026-10-25T02:50:00+02:00",
            ],
            {"tasks": [twice]},
        ),
        ok(
            "only a from",
            ["tasks", "list", "--from", "2026-10-26"],
            {"tasks": [gap]},
        ),
        ok(
            "only a to",
            ["tasks", "list", "--to", "2026-10-02T12:00"],
            {"tasks": [millis]},
        ),
        ok(
            "titles are trimmed as the app trims them, and blank notes are none",
            add + ["﻿  Trim me  ", "--notes", " \n "],
            {"task": trimmed, "sync": local(7)},
            queued=[created_todo(T[7], "Trim me")],
        ),
        fails(
            "a day the calendar doesn't have",
            add + ["Bad", "--start", "2026-02-30T10:00"],
            "invalid",
            bad_time("2026-02-30T10:00"),
        ),
        fails(
            "--start takes a time, not a day",
            add + ["Bad", "--start", "2026-10-02"],
            "invalid",
            bad_time("2026-10-02"),
        ),
        fails(
            "an hour past 23",
            add + ["Bad", "--start", "2026-10-02T24:00"],
            "invalid",
            bad_time("2026-10-02T24:00"),
        ),
        fails(
            "an offset without its colon",
            add + ["Bad", "--start", "2026-10-02T10:00+0200"],
            "invalid",
            bad_time("2026-10-02T10:00+0200"),
        ),
        fails(
            "a space for the T",
            add + ["Bad", "--start", "2026-10-02 10:00"],
            "invalid",
            bad_time("2026-10-02 10:00"),
        ),
        fails(
            "--day takes a day, not a time",
            add + ["Bad", "--day", "2026-10-02T10:00"],
            "invalid",
            'Can\'t read "2026-10-02T10:00" as a day. Use 2026-10-01.',
        ),
        fails(
            "an end at the start",
            add + ["Bad", "--start", "2026-10-02T10:00", "--end", "2026-10-02T10:00"],
            "invalid",
            "The end must be after the start.",
        ),
        fails(
            "an end before the start, across offsets",
            add + ["Bad", "--start", "2026-10-02T10:00", "--end", "2026-10-02T07:30:00Z"],
            "invalid",
            "The end must be after the start.",
        ),
        fails(
            "a range that can't be read",
            ["tasks", "list", "--from", "yesterday"],
            "invalid",
            bad_moment("yesterday"),
        ),
        fails(
            "a deadline that can't be read",
            add + ["Bad", "--deadline", "soon"],
            "invalid",
            bad_moment("soon"),
        ),
        ok("only what worked was saved", ["status"], status(None, local(7), False)),
    ]


# --------------------------------------------------------------------------------------------
# What it refuses. A command that fails changes nothing.


def refusals():
    usage = "usage"
    return [
        fails(
            "no command",
            [],
            usage,
            f"No command given. {HINT}",
            given={"now": "2026-10-01T07:40:00Z", "account": None, "appRunning": False},
        ),
        fails("an option for a command", ["--status"], usage, f"No command given. {HINT}"),
        fails("an unknown command", ["frob"], usage, f'Unknown command "frob". {HINT}'),
        fails("half a command", ["tasks"], usage, f'Unknown command "tasks". {HINT}'),
        fails(
            "an unknown subcommand",
            ["tasks", "frob", "x"],
            usage,
            f'Unknown command "tasks frob". {HINT}',
        ),
        fails(
            "an unknown option",
            ["tasks", "list", "--bogus"],
            usage,
            'Unknown option --bogus for "tasks list".',
        ),
        fails(
            "an option of another command",
            ["tasks", "show", "x", "--title", "y"],
            usage,
            'Unknown option --title for "tasks show".',
        ),
        fails("a missing title", ["tasks", "add"], usage, '"tasks add" needs --title.'),
        fails(
            "an option without its value",
            ["tasks", "add", "--title"],
            usage,
            "--title needs a value.",
        ),
        fails(
            "an option twice",
            ["tasks", "add", "--title", "a", "--title=b"],
            usage,
            "--title is given twice.",
        ),
        fails(
            "a flag twice",
            ["tasks", "list", "--unscheduled", "--unscheduled"],
            usage,
            "--unscheduled is given twice.",
        ),
        fails("a flag with a value", ["sync", "--open=1"], usage, "--open takes no value."),
        fails(
            "a day and a time",
            ["tasks", "add", "--title", "x", "--day", "2026-10-02", "--start", "2026-10-02T10:00"],
            usage,
            "--day can't be combined with --start or --end.",
        ),
        fails(
            "an end without a start",
            ["tasks", "add", "--title", "x", "--end", "2026-10-02T10:00"],
            usage,
            "--end needs --start.",
        ),
        fails(
            "a deadline and a session",
            ["tasks", "add", "--title", "x", "--deadline", "2026-10-02", "--day", "2026-10-02"],
            usage,
            "--deadline can't be combined with --start, --end or --day.",
        ),
        fails("a missing id", ["tasks", "show"], usage, '"tasks show" needs a task id.'),
        fails(
            "an id too many",
            ["tasks", "show", "a", "b"],
            usage,
            'Unexpected argument "b".',
        ),
        fails(
            "an argument for a command without one",
            ["status", "now"],
            usage,
            'Unexpected argument "now".',
        ),
        fails(
            "an update without a change",
            ["tasks", "update", "x"],
            usage,
            '"tasks update" needs at least one of --title, --notes, --project, --estimate, '
            "--deadline.",
        ),
        fails(
            "a schedule without a time",
            ["tasks", "schedule", "x"],
            usage,
            '"tasks schedule" needs --start or --day.',
        ),
        fails("a project without a name", ["projects", "add"], usage, '"projects add" needs --name.'),
        fails(
            "a blank title", ["tasks", "add", "--title", "   "], "invalid", "A task needs a title."
        ),
        fails(
            "a blank project name",
            ["projects", "add", "--name", " "],
            "invalid",
            "A project needs a name.",
        ),
        fails(
            "an estimate of zero",
            ["tasks", "add", "--title", "x", "--estimate", "0"],
            "invalid",
            "The estimate is a whole number of minutes from 1 to 10080.",
        ),
        fails(
            "an estimate over a week",
            ["tasks", "add", "--title", "x", "--estimate", "10081"],
            "invalid",
            "The estimate is a whole number of minutes from 1 to 10080.",
        ),
        fails(
            "an estimate in words",
            ["tasks", "add", "--title", "x", "--estimate", "1h"],
            "invalid",
            "The estimate is a whole number of minutes from 1 to 10080.",
        ),
        fails(
            "an unknown status",
            ["tasks", "list", "--status", "done"],
            "invalid",
            "--status is open, completed or all.",
        ),
        fails(
            "an unknown color",
            ["projects", "add", "--name", "x", "--color", "mauve"],
            "invalid",
            'Can\'t read "mauve" as a color. Use blue, green, orange, purple, pink, teal, yellow, '
            "gray or #rrggbb.",
        ),
        fails(
            "a color that isn't six hex digits",
            ["projects", "add", "--name", "x", "--color", "#12345g"],
            "invalid",
            'Can\'t read "#12345g" as a color. Use blue, green, orange, purple, pink, teal, '
            "yellow, gray or #rrggbb.",
        ),
        fails(
            "a project that isn't there",
            ["tasks", "add", "--title", "x", "--project", "nope"],
            "notFound",
            'No project with id "nope".',
        ),
        fails(
            "a list for a project that isn't there",
            ["tasks", "list", "--project", "nope"],
            "notFound",
            'No project with id "nope".',
        ),
        fails("showing a task that isn't there", ["tasks", "show", "nope"], "notFound", no_task("nope")),
        fails(
            "updating one",
            ["tasks", "update", "nope", "--title", "x"],
            "notFound",
            no_task("nope"),
        ),
        fails(
            "scheduling one",
            ["tasks", "schedule", "nope", "--day", "2026-10-02"],
            "notFound",
            no_task("nope"),
        ),
        fails("unscheduling one", ["tasks", "unschedule", "nope"], "notFound", no_task("nope")),
        fails("completing one", ["tasks", "complete", "nope"], "notFound", no_task("nope")),
        fails("reopening one", ["tasks", "reopen", "nope"], "notFound", no_task("nope")),
        fails("deleting one", ["tasks", "delete", "nope"], "notFound", no_task("nope")),
        ok("help is text", ["help"], HELP),
        ok("nothing was saved", ["status"], status(None, local(0), False)),
        ok("no task", ["tasks", "list", "--status", "all"], {"tasks": []}),
        ok("no project", ["projects", "list"], {"projects": []}),
    ]


# --------------------------------------------------------------------------------------------
# Project colors: each new project takes the first color no project uses; once all eight are
# used they repeat, by how many projects there are.


def project_colors():
    colors = [
        ("Blue", "#4f8ef7"),
        ("Green", "#3fb86a"),
        ("Orange", "#e8893a"),
        ("Purple", "#9b7bf0"),
        ("Pink", "#e0609b"),
        ("Teal", "#2fb3b0"),
        ("Yellow", "#d9b43a"),
        ("Gray", "#8a8d96"),
        ("Ninth", "#4f8ef7"),
    ]
    steps = []
    for index, (name, color) in enumerate(colors):
        given = {"ids": [P[index + 1]]}
        if index == 0:
            given.update({"now": "2026-10-01T07:40:00Z", "account": None, "appRunning": False})
        steps.append(
            ok(
                f"project {index + 1} is {color}",
                ["projects", "add", "--name", name],
                {"project": project(P[index + 1], name, color), "sync": local(index + 1)},
                given=given,
                queued=[created_project(P[index + 1], name, color)],
            )
        )
    steps.append(
        ok(
            "a color given by name is that color, whatever is used",
            ["projects", "add", "--name", "Tenth", "--color", "gray"],
            {"project": project(uuid("b1"), "Tenth", "#8a8d96"), "sync": local(10)},
            given={"ids": [uuid("b1")]},
            queued=[created_project(uuid("b1"), "Tenth", "#8a8d96")],
        )
    )
    return steps


TRANSCRIPT = {
    "contract": 1,
    "timeZone": "Europe/Warsaw",
    "appVersion": "0.1.0",
    "scenes": [
        {"name": "signed out", "steps": signed_out()},
        {"name": "premium with the app running", "steps": premium_running()},
        {"name": "where a change goes", "steps": where_changes_go()},
        {"name": "times", "steps": times()},
        {"name": "refusals", "steps": refusals()},
        {"name": "project colors", "steps": project_colors()},
    ],
}


def main():
    text = json.dumps(TRANSCRIPT, indent=2, ensure_ascii=False) + "\n"
    path = HERE / "transcript.json"
    if "--check" in sys.argv:
        if not path.exists() or path.read_text() != text:
            sys.exit("contract/transcript.json is out of date: run python3 contract/transcript.py")
        return
    path.write_text(text)
    steps = sum(len(scene["steps"]) for scene in TRANSCRIPT["scenes"])
    print(f"wrote {path.name}: {len(TRANSCRIPT['scenes'])} scenes, {steps} steps")


if __name__ == "__main__":
    main()
