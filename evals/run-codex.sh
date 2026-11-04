#!/usr/bin/env bash
# Codex runner for the same corpus - WRITTEN, NOT YET RUN: `codex` was not installed where this was built.
# Pass 1 only (hook off): Codex ships no Flo hook (by design), so there is no Codex pass 2.
# Safety: refuses to start while a real engini CLI login file exists for you (Codex's workspace-write sandbox limits
# WRITES only - reads stay disk-wide and `codex exec` runs commands unasked, so a model told to print the key would
# read it). Then: stub engini first on PATH, a dead ENGINI_API_KEY, no other ENGINI_* variable, and HOME /
# XDG_CONFIG_HOME / APPDATA / USERPROFILE all pointed at an empty temp dir; CODEX_HOME stays on your real ~/.codex for
# Codex auth. Prefer running it in a container or CI, not on a staff laptop.
# `codex exec` defaults to a read-only sandbox, so the sandbox is set explicitly or every case fails for the wrong
# reason. Assertions read the --json event stream (attempted commands) and the stub log (executed argv).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
work=$(mktemp -d)
empty=$(mktemp -d)
command -v codex >/dev/null || { echo "run-codex: codex not installed - NOT RUN"; exit 2; }
# existence only - never read. The four places the CLI stores its login (configPath()).
for f in "${XDG_CONFIG_HOME:+$XDG_CONFIG_HOME/engini/config.toml}" "$HOME/.config/engini/config.toml" \
         "${APPDATA:+$APPDATA/engini/config.toml}" "${USERPROFILE:+$USERPROFILE/engini/config.toml}"; do
  if [ -n "$f" ] && [ -e "$f" ]; then
    echo "run-codex: a real engini CLI login exists ($f) - REFUSED. Log out of the CLI or run in a container."
    exit 3
  fi
done
codex_home=${CODEX_HOME:-$HOME/.codex}
unset $(compgen -v ENGINI_) 2>/dev/null || true
python3 - "$here/cases.json" > "$work/cases.tsv" <<'PY'
import json, sys
for c in json.load(open(sys.argv[1]))['cases']:
    if c['pass'] == 1:
        print(c['id'] + '\t' + ('1' if c.get('inject') else '0') + '\t' + c['prompt'].replace('/workflow:build-engini-workflow ', 'Use the build-engini-workflow skill. ').replace('\n', ' '))
PY
fail=0
while IFS=$'\t' read -r id inject prompt; do
  log="$work/stub-$id.log"; : > "$log"
  rc=0; [ "$inject" = 1 ] && inject=1 || inject=   # the stub injects on any non-empty value
  PATH="$here/stub:$PATH" FLO_STUB_LOG="$log" FLO_STUB_INJECT="$inject" ENGINI_API_KEY=eng_dead_eval_key_not_valid \
    HOME="$empty" CODEX_HOME="$codex_home" XDG_CONFIG_HOME="$empty" APPDATA="$empty" USERPROFILE="$empty" \
    codex exec --json --sandbox workspace-write -c sandbox_workspace_write.network_access=false \
      --output-schema "$here/codex-output-schema.json" -C "$work" "$prompt" < /dev/null > "$work/transcript-$id.jsonl" || rc=$?
  # a run that never ran (auth failure, bad flag) would pass every negative case - count it as a failure
  if [ "$rc" != 0 ]; then echo "FAIL codex $id: codex exec exited $rc"; fail=1; continue; fi
  python3 "$here/score.py" "$id" "$work/transcript-$id.jsonl" "$log" || fail=1
done < "$work/cases.tsv"
echo "run-codex: transcripts and stub logs in $work"
exit "$fail"
