#!/usr/bin/env bash
# End to end on a Mac, with a window: a stubbed Debug build of Unfold on a throwaway database, and
# the skill's launcher. It proves what no unit test can: two processes, the notification between
# them, and the app's sync sending what the command line wrote.
#
#   1. No app on the database: a change waits (`pending`), `sync --open` starts the app, and the
#      app sends it.
#   2. The app running: a change is `syncing`, and the app sends it within seconds.
#
# Nothing of the user's is read or written, and no account or network is used. An Unfold the user
# has open runs on its own database, so the command line doesn't count it, and this leaves it
# alone.
#
#   (cd ../unfold && make build)      # or any Debug build, see UNFOLD_MAC_APP
#   scripts/e2e-mac.sh
set -euo pipefail
cd "$(dirname "$0")/.."

app=${UNFOLD_MAC_APP:-../unfold/.build/xcode/Build/Products/Debug/Unfold.app}
if [ ! -x "$app/Contents/MacOS/Unfold" ]; then
  echo "no Debug build of Unfold at $app" >&2
  exit 1
fi
# Only a Debug build follows UNFOLD_DATABASE and the stubs: any other would write to the real
# database and sync with the real account. So it runs only an app that says it's one, before any
# command; an app that says nothing is from before it did.
configuration=$(plutil -extract UnfoldBuildConfiguration raw -o - "$app/Contents/Info.plist" 2>/dev/null || true)
if [ "$configuration" != Debug ]; then
  echo "$app isn't a Debug build (UnfoldBuildConfiguration: ${configuration:-none}), so it would use the real data" >&2
  exit 1
fi
app=$(cd "$app" && pwd)

# The app is sandboxed: its files live in its container, and only it creates this one. A stubbed
# command line starts a stubbed app, so `sync --open` never opens one on the real data.
database="$HOME/Library/Containers/com.unfoldplanner.mac/Data/tmp/unfold-skill-e2e-$$/Unfold.sqlite"
export UNFOLD_APP=$app UNFOLD_AUTH_STUB=signedIn UNFOLD_PLAN_STUB=premium UNFOLD_DATABASE=$database
unfold() { sh skills/unfold/scripts/unfold "$@"; }
field() { sed -n "s/.*\"$1\":\\([^,}]*\\).*/\\1/p"; }
# The processes of this build; those that ran before this script are the user's, and stay.
builds() { pgrep -f "$app/Contents/MacOS/Unfold" || true; }
before=" $(builds | tr '\n' ' ') "
stop_ours() {
  for pid in $(builds); do
    case "$before" in
      *" $pid "*) ;;
      *) kill "$pid" 2>/dev/null || true ;;
    esac
  done
}
trap stop_ours EXIT

# Waits up to ten seconds for the app to have sent everything.
drained() {
  for _ in $(seq 1 20); do
    [ "$(unfold status | field pendingChanges)" = 0 ] && return 0
    sleep 0.5
  done
  echo "the app didn't send the change within 10 seconds" >&2
  return 1
}

expect_state() {
  case "$2" in
    *"\"state\":\"$1\""*) ;;
    *) echo "expected the state $1, got: $2" >&2; exit 1 ;;
  esac
}

# A new database has no app on it, whatever else is open.
[ "$(unfold status | field running)" = false ] || { echo "an app already runs on $database" >&2; exit 1; }
expect_state pending "$(unfold tasks add --title "Added while Unfold was closed")"
opened=$(unfold sync --open)
expect_state syncing "$opened"
[ "$(printf '%s' "$opened" | field opened)" = true ] || { echo "sync --open didn't open: $opened" >&2; exit 1; }
[ "$(unfold status | field running)" = true ] || { echo "the app sync --open started isn't running" >&2; exit 1; }
drained
echo "ok: with Unfold closed, sync --open started it and it sent the change"

expect_state syncing "$(unfold tasks add --title "Added while Unfold was running" --start 2026-10-02T09:00)"
drained
echo "ok: with Unfold running, it sent the change the command line made"
