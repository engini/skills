#!/usr/bin/env python3
"""Table-driven self-test for plugin/hooks/deny-never-verbs.py. Not shipped.

  python3 tools/hook-selftest.py [--hook PATH] [--quiet]

Each row is one assertion with concrete input and one of three outcomes: allow, ask (the user is asked to confirm)
or deny (the agent is refused). Exit 1 on any failure, naming the row.
Also: the hook's stdout carries the right permissionDecision, a 2 MB input returns in under 1 s, and against
tools/contract/snapshot.json `tools call` asks for exactly the never-verbs in tools/rules.json and is allowed for
every other live slug.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # importing the hook must not drop a __pycache__ into the payload
CFG = '~/.config/engini'  # the key directory, spelled once


def B(cmd, tool='Bash'):
    return json.dumps({'tool_name': tool, 'tool_input': {'command': cmd}})


def F(tool, path, **extra):
    ti = dict(extra)
    ti['notebook_path' if tool == 'NotebookEdit' else 'file_path'] = path
    return json.dumps({'tool_name': tool, 'tool_input': ti})


def S(tool, **ti):
    return json.dumps({'tool_name': tool, 'tool_input': ti})


PLAN_BODY = ('{"plan":{"name":"Leads","notes":"never engini tools call engini_workflows_delete_workflow; '
             'run $(x) and connect later","steps":[]}}')
SHIPPED = ("engini tools call engini_workflows_create_workflow_from_plan --args - --connection 7 --max-bytes 0 <<'EOF'\n"
           + PLAN_BODY + "\nEOF")
NV = 'engini_workflows_delete_workflow'

# (expect: allow|ask|deny, family, label, payload, reason-kind or None). reason-kind: never | unreadable | rawkey | keyread | self | bad
ROWS = [
    # ---- family 1: the four never-verbs through `tools call`
    ('ask', '1', 'plain', B('engini tools call engini_workflows_delete_workflow --args - --max-bytes 0'), 'never'),
    ('ask', '1', 'compound cd', B('cd /tmp && engini tools call engini_workflows_run_workflow --args -'), 'never'),
    ('ask', '1', 'bash -c', B('bash -c "engini tools call engini_workflows_rerun_execution --args -"'), 'never'),
    ('ask', '1', 'npx', B('npx @engini/cli tools call engini_workflows_enable_or_disable_workflow --args -'), 'never'),
    ('ask', '1', 'node cli.js', B('node ./node_modules/@engini/cli/dist/cli.js tools call engini_workflows_run_workflow'), 'never'),
    ('ask', '1', 'variable slug $V', B('V=delete_workflow; engini tools call engini_workflows_$V --args -'), 'unreadable'),
    ('ask', '1', 'double-quoted', B('engini tools call "engini_workflows_delete_workflow" --args -'), 'never'),
    ('ask', '1', 'upper case', B('engini tools call ENGINI_WORKFLOWS_DELETE_WORKFLOW --args -'), 'never'),
    ('ask', '1', "del''ete", B("engini tools call engini_workflows_del''ete_workflow --args -"), 'never'),
    ('ask', '1', 'glued paren', B('(engini tools call engini_workflows_delete_workflow)'), None),
    ('ask', '1', 'glued redirect', B('engini tools call engini_workflows_delete_workflow>/dev/null --args -'), None),
    ('ask', '1', 'brace expansion', B('engini tools call engini_workflows_{delete,run}_workflow --args -'), None),
    ('ask', '1', 'brace hides prefix', B('engini tools call engini_{workflows_delete_workflow,x} --args -'), 'unreadable'),
    ('ask', '1', 'later positional $(cat)', B('engini tools call --args - $(cat slug.txt)'), 'unreadable'),
    ('ask', '1', 'later positional "$S"', B('engini tools call --connection 3 "$S"'), 'unreadable'),
    ('ask', '1', 'later positional ${P}', B('engini tools call --connection 3 ${P}delete_workflow'), 'unreadable'),
    ('ask', '1', 'split word $C', B('C=call; engini tools $C engini_workflows_delete_workflow --args -'), None),
    ('ask', '1', "t''ools c''all", B("engini t''ools c''all engini_workflows_del''ete_workflow --args -"), 'never'),
    ('ask', '1', 'pwsh backticks', B('engini tools ca`ll engini_workflows_del`ete_workflow --args -', 'PowerShell'), 'never'),
    ('ask', '1', 'second line', B('engini tools call engini_workflows_get_workflows --args -\nengini tools call engini_workflows_delete_workflow --args -'), 'never'),
    ('ask', '1', 'joined by &', B('engini tools call engini_workflows_get_workflows & engini tools call engini_workflows_delete_workflow --args -'), 'never'),
    ('ask', '1', 'nested $( )', B('engini tools call engini_workflows_get_workflows --args "$(engini tools call engini_workflows_delete_workflow --args -)"'), 'never'),
    ('ask', '1', 'fake heredoc bash', B("bash <<'EOF'\nengini tools call engini_workflows_delete_workflow --args -\nEOF"), 'never'),
    ('ask', '1', 'fake heredoc sh', B("sh <<'EOF'\nengini tools call engini_workflows_delete_workflow --args -\nEOF"), 'never'),
    ('ask', '1', 'fake heredoc python3 -', B('python3 - <<EOF\nimport os; os.system("engini tools call engini_workflows_delete_workflow --args -")\nEOF'), 'never'),
    ('ask', '1', 'fake heredoc source', B('source /dev/stdin <<EOF\nengini tools call engini_workflows_delete_workflow --args -\nEOF'), 'never'),
    ('ask', '1', 'unquoted cat heredoc $( )', B('cat <<EOF\n$(engini tools call engini_workflows_delete_workflow --args -)\nEOF'), 'never'),
    ('ask', '1', 'herestring <<<', B('cat <<<EOF\nengini tools call engini_workflows_delete_workflow\nEOF'), 'never'),
    ('ask', '1', "<<'EO'F renamed delimiter", B("cat <<'EO'F >/dev/null\nEOF\nengini tools call engini_workflows_delete_workflow\nEO"), 'never'),
    ('ask', '1', 'command after opener', B("cat <<'EOF' && engini tools call engini_workflows_delete_workflow"), 'never'),
    ('ask', '1', 'heredoc not owned by the call', B("engini tools call slack_send_message --args - ; bash <<'EOF'\nengini tools call engini_workflows_delete_workflow --args -\nEOF"), 'never'),
    ('ask', '1', 'never-verb heredoc washes nothing', B("engini tools call engini_workflows_delete_workflow --args - <<'EOF'\n{}\nEOF"), 'never'),
    # heredoc shapes bash runs as commands - the strip must leave each body in and scan it
    ('ask', '1', 'heredoc read by sh -s', B("sh -s tools call slack_send_message --args - <<'EOF'\n" + "engini tools call %s --args -\nEOF" % NV), 'never'),
    ('ask', '1', 'heredoc read by bash -s', B("bash -s tools call slack_send_message --args - <<'EOF'\n" + "engini tools call %s --args -\nEOF" % NV), 'never'),
    ('ask', '1', '# comments out the opener', B("engini tools call engini_workflows_get_workflows --args - --max-bytes #<<'EOF'\n" + "engini tools call %s --args -\nEOF" % NV), 'never'),
    ('ask', '1', 'backslash ends a quoted body line', B("engini tools call engini_workflows_get_workflows --args - <<'EOF'\n{}\\\nEOF\n" + "engini tools call %s --args -\nEOF" % NV), 'never'),
    ('ask', '1', 'opener inside an earlier quote', B('echo "\n' + "engini tools call engini_workflows_get_workflows --args - <<'EOF'\n" + '" ; engini tools call %s --args -\nEOF' % NV), 'never'),
    ('ask', '1', 'backslash via the fingerprint', B("shasum -a 256 <<'EOF'\nx\\\nEOF\n" + "engini tools call %s --args -\nEOF" % NV), 'never'),
    ('ask', '1', 'env prefix owns the heredoc', B("env engini tools call engini_workflows_get_workflows --args - <<'EOF'\n" + "engini tools call %s --args -\nEOF" % NV), 'never'),
    ('ask', '1', 'README install canary', B('d=$(mktemp -d) && printf \'#!/bin/sh\\necho FLO-CANARY-RAN\\n\' > "$d/engini" && chmod +x "$d/engini" && PATH="$d:$PATH" engini tools call engini_workflows_delete_workflow --args -'), 'never'),
    # ---- family 1b: a never-verb named outside `tools call`
    ('ask', '1b', 'flags-first', B('engini tools call --connection 3 engini_workflows_delete_workflow --args -'), 'never'),
    ('ask', '1b', 'curl body', B('curl -d \'{"slug":"engini_workflows_delete_workflow"}\' https://x'), None),
    ('ask', '1b', 'python -c', B('python -c "print(\'engini_workflows_run_workflow\')"'), None),
    ('ask', '1b', 'echo $V', B('echo engini_workflows_$V'), 'unreadable'),
    ('ask', '1b', 'cover: quoted tools get', B('engini tools call --connection 3 engini_workflows_delete_workflow --note "engini tools get engini_workflows_delete_workflow"'), 'never'),
    ('ask', '1b', 'cover: split tools/get', B('engini tools call --connection tools --toolset get engini_workflows_delete_workflow'), 'never'),
    ('ask', '1b', 'cover: tools get exempts i+2 only', B('engini tools get engini_workflows_get_workflow engini_workflows_delete_workflow'), 'never'),
    # ---- family 2: raw-key commands
    ('deny', '2', 'connect --field', B('engini connect engini_workflows --field api_key=eng_x'), 'rawkey'),
    ('deny', '2', 'connections update', B('engini connections update 3 --field api_key=x'), 'rawkey'),
    ('deny', '2', 'connections create', B('engini connections create --application engini_workflows'), 'rawkey'),
    ('deny', '2', 'connections delete', B('engini connections delete 3'), 'rawkey'),
    ('deny', '2', 'auth-providers create', B('engini connections auth-providers create --field Secret=x'), 'rawkey'),
    ('deny', '2', 'login --api-key', B('engini login --api-key eng_x --force'), 'rawkey'),
    ('deny', '2', 'flag before subcommand', B('engini --json connections delete 3'), 'rawkey'),
    # ---- family 3: the key directory, every platform form
    ('deny', '3', 'Read posix', F('Read', CFG + '/config.toml'), 'keyread'),
    ('deny', '3', 'Edit posix', F('Edit', CFG + '/config.toml'), 'keyread'),
    ('deny', '3', 'Write posix', F('Write', CFG + '/config.toml'), 'keyread'),
    ('deny', '3', 'Grep posix dir', S('Grep', pattern='api_key', path=CFG), 'keyread'),
    ('deny', '3', 'Read %APPDATA%', F('Read', '%APPDATA%\\engini\\config.toml'), 'keyread'),
    ('deny', '3', 'Edit %APPDATA%', F('Edit', '%APPDATA%\\engini\\config.toml'), 'keyread'),
    ('deny', '3', 'Write %APPDATA%', F('Write', '%APPDATA%\\engini\\config.toml'), 'keyread'),
    ('deny', '3', 'Grep %APPDATA% dir', S('Grep', pattern='api_key', path='%APPDATA%\\engini'), 'keyread'),
    ('deny', '3', 'Read homedir form', F('Read', '~/engini/config.toml'), 'keyread'),
    ('deny', '3', 'Edit homedir form', F('Edit', '~/engini/config.toml'), 'keyread'),
    ('deny', '3', 'Write homedir form', F('Write', '~/engini/config.toml'), 'keyread'),
    ('deny', '3', 'Grep homedir form', S('Grep', pattern='x', path='~/engini/config.toml'), 'keyread'),
    ('deny', '3', 'Read AppData/Roaming', F('Read', '/c/Users/x/AppData/Roaming/engini/config.toml'), 'keyread'),
    ('deny', '3', 'Edit AppData/Roaming', F('Edit', '/c/Users/x/AppData/Roaming/engini/config.toml'), 'keyread'),
    ('deny', '3', 'Write AppData/Roaming', F('Write', '/c/Users/x/AppData/Roaming/engini/config.toml'), 'keyread'),
    ('deny', '3', 'Grep AppData/Roaming dir', S('Grep', pattern='x', path='/c/Users/x/AppData/Roaming/engini'), 'keyread'),
    ('deny', '3', 'Glob pattern', S('Glob', pattern=CFG + '/*'), 'keyread'),
    ('deny', '3', 'Grep parent + glob', S('Grep', pattern='api_key', path='~/.config', glob='engini/*'), 'keyread'),
    ('deny', '3', 'Grep parent, recursive', S('Grep', pattern='api_key', path='~/.config'), 'keyread'),
    ('deny', '3', 'Grep home', S('Grep', pattern='api_key', path='/Users/x/'), 'keyread'),
    ('deny', '3', 'Grep %APPDATA%', S('Grep', pattern='api_key', path='%APPDATA%'), 'keyread'),
    ('deny', '3', 'Glob from home', S('Glob', pattern='**/config.toml', path='~'), 'keyread'),
    ('deny', '3', 'grep -r dir', B('grep -r api_key ' + CFG + '/'), 'keyread'),
    ('deny', '3', 'cd then cat', B('cd ' + CFG + ' && cat config.toml'), 'keyread'),
    ('deny', '3', '$XDG_CONFIG_HOME form', B('cat ${XDG_CONFIG_HOME}/engini/config.toml'), 'keyread'),
    ('deny', '3', 'quote-split path', B("cat ~/.con''fig/eng''ini/config.toml"), 'keyread'),
    # ---- family 4: key variables and env dumps
    ('deny', '4', 'printenv var', B('printenv ENGINI_API_KEY'), 'keyread'),
    ('deny', '4', 'echo var', B('echo "$ENGINI_API_KEY"'), 'keyread'),
    ('deny', '4', 'bare env', B('env'), 'keyread'),
    ('deny', '4', 'env piped', B('env | grep ENG'), 'keyread'),
    ('deny', '4', 'export -p', B('export -p'), 'keyread'),
    ('deny', '4', 'declare -p', B('declare -p'), 'keyread'),
    ('deny', '4', 'bare set', B('set'), 'keyread'),
    ('deny', '4', '/proc environ', B('cat /proc/self/environ'), 'keyread'),
    ('deny', '4', 'API_TOKEN', B('echo $ENGINI_API_TOKEN'), 'keyread'),
    ('deny', '4', 'pwsh Env: drive', B('Get-ChildItem Env:', 'PowerShell'), 'keyread'),
    ('deny', '4', 'presence test then echo', B('[ -n "$ENGINI_API_KEY" ] && echo $ENGINI_API_KEY'), 'keyread'),
    ('deny', '4', 'substring oracle', B('[ -n "${ENGINI_API_KEY:3:1}" ]'), 'keyread'),
    ('deny', '4', 'substitution in test', B('[ -n "$(echo $ENGINI_API_KEY >&2)" ]'), 'keyread'),
    # ---- family 5: self-protection
    ('deny', '5', 'Edit user settings', F('Edit', '~/.claude/settings.json'), 'self'),
    ('deny', '5', 'Write hook script', F('Write', '/h/.claude/plugins/cache/engini/workflow/0.3.0/hooks/deny-never-verbs.py'), 'self'),
    ('deny', '5', 'sed claude-hooks.json', B('sed -i s/x/y/ ~/.claude/plugins/cache/workflow/hooks/claude-hooks.json'), 'self'),
    ('deny', '5', 'sed bare hooks.json', B('sed -i s/x/y/ ./plugin-copy/hooks/hooks.json'), 'self'),
    ('deny', '5', 'sed codex-hooks.json', B('sed -i s/x/y/ ./plugin-copy/hooks/codex-hooks.json'), 'self'),
    ('deny', '5', 'Write .codex config', F('Write', '/h/.codex/config.toml'), 'self'),
    ('deny', '5', 'cd ~/.claude then write', B('cd ~/.claude && echo \'{"disableAllHooks":true}\' > settings.local.json'), 'self'),
    ('deny', '5', 'cd ~/.claude; python open', B('cd ~/.claude; python3 -c "open(\'settings.json\',\'a\').write(\'x\')"'), 'self'),
    ('deny', '5', 'glob settings name', B('echo \'{"disableAllHooks":true}\' > ~/.claude/sett?ngs.local.json'), 'self'),
    ('deny', '5', 'cd ~/.codex then write', B('cd ~/.codex && echo x > config.toml'), 'self'),
    ('deny', '5', 'disableAllHooks via bash', B('echo \'{"disableAllHooks":true}\' > ~/.claude/settings.local.json'), 'self'),
    # a `.` or `..` segment walks past the name patterns
    ('deny', '5', 'dot segment in settings path', B('echo \'{"disableAllHooks":true}\' > ~/.claude/./settings.local.json'), 'self'),
    ('deny', '5', 'cd subfolder/.. then write', B('cd ~/.claude/projects/.. && echo \'{"disableAllHooks":true}\' > settings.json'), 'self'),
    ('deny', '5', 'cd ~/.claude/. then write', B('cd ~/.claude/. && echo x > settings.local.json'), 'self'),
    ('deny', '5', 'tee through /./', B('echo x | tee ~/.claude/./settings.json'), 'self'),
    ('deny', '5', 'Write through /./', F('Write', '/Users/x/.claude/./settings.json', content='{}'), 'self'),
    ('deny', '5', 'Edit through x/..', F('Edit', '/Users/x/.claude/projects/../settings.json', old_string='a', new_string='b'), 'self'),
    ('deny', '5', 'cd subfolder, then cd ..', B('cd ~/.claude/projects && cd .. && echo x > settings.json'), 'self'),
    ('deny', '5', 'windows /./ form', B('echo x > %USERPROFILE%\\.claude\\.\\settings.json', 'PowerShell'), 'self'),
    ('deny', '5', '~user form with x/..', B('echo x > ~someone/.claude/x/../settings.json'), 'self'),
    ('deny', '3', 'key dir through /./', B('cat ~/.config/./engini/c*'), 'keyread'),
    ('deny', '3', 'Read key dir through x/..', F('Read', '~/.config/x/../engini/other'), 'keyread'),
    # ---- a refusal beats a question, in either order and across segments
    ('deny', '2', 'never-verb then login', B('engini tools call engini_workflows_delete_workflow --args - ; engini login'), 'rawkey'),
    ('deny', '2', 'login then never-verb', B('engini login && engini tools call engini_workflows_delete_workflow --args -'), 'rawkey'),
    ('deny', '2', 'unreadable slug then connect', B('engini tools call engini_workflows_$V --args - ; engini connect engini_workflows'), 'rawkey'),
    ('deny', '2', 'never-verb with --api-key', B('engini tools call engini_workflows_run_workflow --api-key x'), 'rawkey'),
    ('deny', '4', 'never-verb and a key read', B('echo $ENGINI_API_KEY; engini tools call engini_workflows_delete_workflow --args -'), 'keyread'),
    ('deny', '5', 'never-verb and a protected file', B('engini tools call engini_workflows_delete_workflow --args - ; echo x > ~/.claude/settings.json'), 'self'),
    # ---- fail-closed
    ('deny', 'fail-closed', 'not json', 'not json', 'bad'),
    ('deny', 'fail-closed', 'null', 'null', 'bad'),
    ('deny', 'fail-closed', '[]', '[]', 'bad'),
    ('deny', 'fail-closed', '{}', '{}', 'bad'),
    ('deny', 'fail-closed', 'no tool_input', '{"tool_name":"Bash"}', 'bad'),
    ('deny', 'fail-closed', 'command not a string', '{"tool_name":"Bash","tool_input":{"command":123}}', 'bad'),
    ('deny', 'fail-closed', 'file_path missing', '{"tool_name":"Edit","tool_input":{}}', 'bad'),
    ('deny', 'fail-closed', 'unknown tool', '{"tool_name":"WebFetch","tool_input":{"url":"https://x"}}', 'bad'),
    ('deny', 'fail-closed', 'empty stdin', '', 'bad'),
    # ---- allow: every slug Flo calls, in the shipped shape
] + [
    ('allow', '1', 'Flo slug ' + s, B('engini tools call engini_workflows_%s --args - --max-bytes 0' % s), None)
    for s in ('search_builder_catalog', 'get_builder_tool_schema', 'get_builder_field_options',
              'list_builder_connections', 'compile_workflow_plan', 'get_workflow_plan', 'create_workflow_from_plan',
              'update_workflow_from_plan', 'get_workflows', 'get_workflow', 'get_workflow_revisions', 'get_folders',
              'get_connections', 'get_executions', 'get_execution', 'get_execution_log', 'get_execution_step_data')
] + [
    # only the four never-verbs: every other slug passes (the four never-verbs ask; nothing else is asked or refused)
    ('allow', '1', 'other slug: another app', B('engini tools call slack_send_message --args -'), None),
    ('allow', '1', 'other slug: newer builder tool', B('engini tools call engini_workflows_purge_everything --args -'), None),
    ('allow', '1', 'other slug: flags first', B('engini tools call --connection 3 engini_workflows_get_workflows'), None),
    ('allow', '1', 'no candidate', B('engini tools call --args - --max-bytes 0'), None),
    ('allow', '1', 'bare tools call', B('engini tools call'), None),
    ('allow', '1', 'git commit message', B('git commit -m "docs: tools call"'), None),
    ('allow', '1', 'git log --grep', B('git log --grep "tools call"'), None),
    ('allow', '1', 'ls tools $(pwd)', B('ls tools $(pwd)'), None),
    ('allow', '1', 'git add tools "$F"', B('git add tools "$F"'), None),
    ('allow', '1', 'inline JSON args', B('engini tools call slack_send_message --args \'{"text":"hi"}\''), None),
    ('allow', '1', 'inline JSON with spaces', B('engini tools call slack_send_message --args \'{"text": "hi there", "n": 2}\''), None),
    ('allow', '1', 'tools get a never-verb', B('engini tools get engini_workflows_delete_workflow --json'), None),
    ('allow', '1', 'tools list', B('engini tools list'), None),
    ('allow', '1', 'get then create', B('engini tools get engini_workflows_delete_workflow && engini tools call engini_workflows_create_workflow_from_plan --args -'), None),
    ('allow', '1', 'commit mentioning tools call', B('git commit -m "fix tools call handling"'), None),
    ('allow', '1', 'bash -c permitted', B('bash -c "engini tools call engini_workflows_get_workflows"'), None),
    ('allow', '1', 'stderr redirect', B('engini tools call engini_workflows_get_folders --args - --connection 7 --max-bytes 0 2>&1'), None),
    ('allow', '1', 'shipped heredoc shape', B(SHIPPED), None),
    # fail closed: the opener must be the command's first line, so a multi-line command scans the body as code
    ('ask', '1', 'shipped shape, not on line 1', B("engini whoami --json\n" + SHIPPED + "\necho done"), 'never'),
    ('allow', '1', 'shipped shape via npx', B(SHIPPED.replace('engini tools', 'npx @engini/cli tools', 1)), None),
    ('allow', '1', 'shipped shape via npx at a version', B(SHIPPED.replace('engini tools', 'npx @engini/cli@1.4.0 tools', 1)), None),
    ('ask', '1', 'npx alias spec reads the body', B(SHIPPED.replace('engini tools', 'npx @engini/cli@npm:zx tools', 1)), 'never'),
    ('ask', '1', 'npx git spec reads the body', B(SHIPPED.replace('engini tools', 'npx @engini/cli@github:a/b tools', 1)), 'never'),
    ('allow', '1', 'shipped shape, command after EOF', B(SHIPPED + "\necho done"), None),
    ('allow', '1', 'fingerprint heredoc', B("shasum -a 256 <<'EOF'\nflo-proposal v1\n" + PLAN_BODY + "\nEOF"), None),
    ('allow', '1', 'heredoc commit message', B("git commit -F - <<'EOF'\nDon't break the build\nEOF"), None),
    ('allow', '2', 'connections list', B('engini connections list --json'), None),
    ('allow', '2', 'connections get', B('engini connections get 3 --json'), None),
    ('allow', '2', 'connections list scoped', B('engini connections list --application engini_workflows --json'), None),
    ('allow', '2', 'npm login is not engini', B('npm login'), None),
    ('allow', '3', 'Flo lessons file', F('Write', '~/.engini/flo/lessons.md'), None),
    ('allow', '3', 'clone path', B('ls ~/engini/proj'), None),
    ('allow', '3', 'README mentions key var', F('Edit', 'README.md', old_string='a', new_string='ENGINI_API_KEY'), None),
    ('allow', '3', 'Read hook script', F('Read', '/h/.claude/plugins/cache/workflow/hooks/deny-never-verbs.py'), None),
    ('allow', '4', 'presence test', B('[ -n "$ENGINI_API_KEY" ]'), None),
    ('allow', '4', 'SKILL.md preflight spelling', B('[ -n "$ENGINI_API_KEY" ] && echo set || echo unset'), None),
    ('deny', '4', 'preflight that echoes the name', B('[ -n "$ENGINI_API_KEY" ] && echo "ENGINI_API_KEY is set"'), 'keyread'),
    ('allow', '4', 'presence -z braces', B('[ -z "${ENGINI_API_KEY}" ]'), None),
    ('allow', '4', 'env FOO=1 engini', B('env FOO=1 engini whoami'), None),
    ('allow', '4', 'set -euo pipefail', B('set -euo pipefail'), None),
    ('allow', '4', '$env:PATH', B('Write-Output $env:PATH', 'PowerShell'), None),
    ('allow', '5', 'ordinary project file', F('Edit', 'src/app.py'), None),
    ('allow', 'smoke', 'whoami', B('engini whoami --json'), None),
    ('allow', 'smoke', 'tools list scoped', B('engini tools list --application engini_workflows'), None),
    ('allow', 'smoke', 'engini --version', B('engini --version'), None),
    ('allow', 'smoke', 'Read a file', F('Read', 'src/app.py'), None),
    ('allow', 'smoke', 'Glob', S('Glob', pattern='**/*.md'), None),
    ('allow', 'smoke', 'Grep', S('Grep', pattern='TODO', path='src'), None),
    ('allow', 'smoke', 'NotebookEdit', F('NotebookEdit', 'a.ipynb', new_source='x'), None),
    ('allow', 'smoke', 'build', B('npm run build && npm test'), None),
    ('allow', '5', 'dot segment outside .claude', B('cd ./src/.. && echo x > ./out.txt'), None),
    ('allow', '5', 'three-dot file name', F('Write', '/h/.claude/agents/.../x.md'), None),
]

# Deliberately OPEN - the hook is a text matcher, not a boundary. The README's residual paragraph names each.
OPEN_ON_PURPOSE = [
    ('glob over the key dir', B('cd ~/.config && cat engini/conf*')),
    ('recursive grep from a parent', B('grep -r api_key ~/.config')),
    ('recursive rg from a parent', B('rg api_key ~/.config')),
    ('wildcard in the settings folder name', B("echo x > ~/.cl*/settings.local.json")),
    ('python straight at the API', B('python3 -c "import urllib.request as u; u.urlopen(\'https://x\')"')),
    ('eval indirection', B('eval "$X"')),
    ('bash -c indirection', B('bash -c "$X"')),
    ('shell function', B('f() { eval "$1"; }; f "$CMD"')),
    ('slug from a file via xargs', B('xargs engini tools call --args - < slugfile')),
    ('another app tool (only the four never-verbs ask)', B('engini tools call slack_send_message --args -')),
]

KINDS = {'never': 'R_NEVER', 'unreadable': 'R_UNREADABLE', 'rawkey': 'R_RAW_KEY', 'keyread': 'R_KEY_READ',
         'self': 'R_SELF', 'bad': 'R_BAD_INPUT'}


def load(path):
    spec = importlib.util.spec_from_file_location('flo_hook', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fs_rows(h):
    """Rows that need a real filesystem: the hook resolves file-tool and Grep/Glob paths against the payload's cwd
    (symlinks, relative paths, alternate home spellings). Built under a throwaway HOME with empty decoy files."""
    import shutil
    import tempfile
    home = os.path.realpath(tempfile.mkdtemp(prefix='flo-selftest-home-'))
    for d in ('.claude', '.config/engini', 'proj/src'):
        os.makedirs(os.path.join(home, d))
    for f in ('.claude/settings.json', '.config/engini/config.toml'):
        open(os.path.join(home, f), 'w').close()
    proj = os.path.join(home, 'proj')
    os.symlink(os.path.join(home, '.claude'), os.path.join(proj, 'c'))
    os.symlink(os.path.join(home, '.config', 'engini'), os.path.join(proj, 'k'))
    os.symlink(home, os.path.join(proj, 'h'))
    elsewhere = os.path.realpath(tempfile.mkdtemp(prefix='flo-selftest-out-'))
    os.symlink(elsewhere, os.path.join(proj, 'out'))

    def P(tool, cwd, **ti):
        return json.dumps({'tool_name': tool, 'tool_input': ti, 'cwd': cwd})

    rows = [
        ('deny', 'Write via a symlink to ~/.claude', P('Write', proj, file_path=proj + '/c/settings.json'), 'self'),
        ('deny', 'Edit, relative, cwd inside ~/.claude', P('Edit', home + '/.claude', file_path='settings.json'), 'self'),
        ('deny', 'Read via a symlink to the key dir', P('Read', proj, file_path=proj + '/k/config.toml'), 'keyread'),
        ('deny', 'Grep relative .. to home', P('Grep', proj, pattern='api_key', path='..'), 'keyread'),
        ('deny', 'Grep empty path, cwd is home', P('Grep', home, pattern='api_key'), 'keyread'),
        ('deny', 'Glob via a symlink to home', P('Glob', proj, pattern='**/*.toml', path='h'), 'keyread'),
        ('deny', 'Grep into the key dir via symlink', P('Grep', proj, pattern='x', path='k'), 'keyread'),
        ('deny', 'Grep ../.. read lexically from a symlinked cwd', P('Grep', proj + '/out', pattern='x', path='../..'), 'keyread'),
        ('allow', 'Grep a project folder', P('Grep', proj, pattern='TODO', path='src'), None),
        ('allow', 'Glob from the project, no path', P('Glob', proj, pattern='**/*.md'), None),
        ('allow', 'Write a project file', P('Write', proj, file_path=proj + '/src/a.py'), None),
    ]
    data = '/System/Volumes/Data'
    if os.path.isdir(data + home):  # macOS firmlink: the same folder under a second name
        rows.append(('deny', 'Grep home via /System/Volumes/Data', P('Grep', proj, pattern='x', path=data + home), 'keyread'))
    saved = {k: os.environ.get(k) for k in ('HOME', 'XDG_CONFIG_HOME', 'APPDATA', 'USERPROFILE', 'CLAUDE_CONFIG_DIR',
                                            'CODEX_HOME')}
    fails = []
    try:
        for k in saved:
            os.environ.pop(k, None)
        os.environ['HOME'] = home
        for expect, label, payload, kind in rows:
            got = h.decide(payload)
            ok = (got is None) if expect == 'allow' else (got == getattr(h, KINDS[kind]) and outcome_ok(h, 'deny', got))
            if not ok:
                fails.append('%-5s fs %s -> %s' % (expect, label, 'allow' if got is None else got[:60]))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(home)
        shutil.rmtree(elsewhere)
    return fails


def outcome_ok(h, expect, got):
    if expect == 'allow':
        return got is None
    if expect == 'ask':
        return got in h.ASK_REASONS and got.startswith(h.ASK_TOKEN)
    return got is not None and got not in h.ASK_REASONS and got.startswith(h.DENY_TOKEN)


def wire_fails(hook_path):
    """The hook as Claude Code runs it: stdin in, one JSON line out. The decision field is what makes Claude Code
    ask or refuse, so it is asserted on the real output, not on decide()."""
    fails = []
    for label, payload, want in (
            ('never-verb', B('engini tools call engini_workflows_delete_workflow --args -'), 'ask'),
            ('unreadable slug', B('engini tools call engini_workflows_$V --args -'), 'ask'),
            ('raw-key command', B('engini login'), 'deny'),
            ('key read', B('echo $ENGINI_API_KEY'), 'deny'),
            ('never-verb + raw key', B('engini tools call engini_workflows_run_workflow --args - ; engini connect x'), 'deny'),
            ('allowed command', B('engini whoami --json'), None)):
        p = subprocess.run([sys.executable, hook_path], input=payload.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = p.stdout.decode()
        try:
            got = json.loads(out)['hookSpecificOutput']['permissionDecision'] if out else None
        except Exception:
            got = 'unparseable'
        if p.returncode != 0 or got != want:
            fails.append('wire: %s -> permissionDecision %r (rc %d), expected %r' % (label, got, p.returncode, want))
    return fails


def reason_fails(h):
    """What each reason tells the reader. The raw-key refusal is the agent's only instruction, so it must send the
    user to their OWN terminal (a `!` command has no terminal: the CLI cannot hide the key) and never suggest a key
    in the command; the ask reasons are for the user and must not read as a refusal."""
    fails = []
    r = h.R_RAW_KEY
    for need in ('OWN terminal', 'outside Claude Code and Codex', 'not with the ! prefix', 'no key in it', 'engini login',
                 'engini connect engini_workflows', 'not ask the user to paste a key'):
        if need not in r:
            fails.append('R_RAW_KEY lost %r' % need)
    if re.search(r'(?<!with the )(?<!not )! ?(engini|login|connect)', r) or 'use the !' in r.lower():
        fails.append('R_RAW_KEY suggests a ! command')
    if re.search(r'engini (login|connect)[^.;)]*--api-key', r):
        fails.append('R_RAW_KEY suggests a command carrying --api-key')
    for name in ('R_NEVER', 'R_UNREADABLE'):
        t = getattr(h, name)
        if not t.startswith(h.ASK_TOKEN) or 'Approve only if' not in t or h.DENY_TOKEN in t:
            fails.append('%s is not a plain ask reason' % name)
    if set(h.ASK_REASONS) != {h.R_NEVER, h.R_UNREADABLE}:
        fails.append('ASK_REASONS is not exactly {R_NEVER, R_UNREADABLE}')
    return fails


def run(hook_path, quiet=False):
    h = load(hook_path)
    fails = []
    for expect, fam, label, payload, kind in ROWS:
        got = h.decide(payload)
        ok = outcome_ok(h, expect, got)
        if ok and kind and got != getattr(h, KINDS[kind]):
            ok = False
        if not ok:
            fails.append('%-5s family %-11s %s -> %s' % (expect, fam, label, 'allow' if got is None else got[:60]))
    for label, payload in OPEN_ON_PURPOSE:
        if h.decide(payload) is not None:
            fails.append('open-on-purpose row now denies (update README residuals): ' + label)
    fails += fs_rows(h)
    fails += reason_fails(h)
    fails += wire_fails(hook_path)
    # undecodable bytes: main() decodes strictly as UTF-8 and denies on failure
    try:
        b'\xff\xfe'.decode('utf-8')
        fails.append('undecodable bytes decoded')
    except UnicodeDecodeError:
        if h.decide('') is None:
            fails.append('fail-closed: undecodable bytes -> empty input allowed')
    # 2 MB command in under 1 s, in the shipped shape and as an unvalidated JSON body
    big = PLAN_BODY[:-2] + ',"pad":"' + ('x y ' * (2 * 1024 * 1024 // 4)) + '"}}'
    # The bar is the shipped shape under 1 s. A 2 MB heredoc the hook may NOT strip is scanned as code, so it
    # gets a looser bar, kept far under the 30 s timeout in plugin/hooks/claude-hooks.json (a timeout fails open).
    for label, cmd, limit in (('2MB shipped heredoc', SHIPPED.replace(PLAN_BODY, big), 1.0),
                              ('2MB unvalidated JSON heredoc', 'cat <<EOF\n' + ('{"k": "v w", "n": [1, 2]} ' * 80000) + '\nEOF', 5.0)):
        t = time.time()
        h.decide(B(cmd))
        dt = time.time() - t
        if dt >= limit:
            fails.append('%s took %.2fs (>= %.0f s; a hook timeout fails open)' % (label, dt, limit))
        elif not quiet:
            print('timing: %s %.2fs (limit %.0f s)' % (label, dt, limit))
    # the 21-slug contract snapshot: asked for exactly the never-verbs, allowed for the rest
    with open(os.path.join(ROOT, 'tools/rules.json'), encoding='utf-8') as f:
        never = set(json.load(f)['never_verbs'])
    with open(os.path.join(ROOT, 'tools/contract/snapshot.json'), encoding='utf-8') as f:
        slugs = sorted(json.load(f)['tools'])
    if not never <= set(slugs):
        fails.append('snapshot is missing never-verbs: %s' % sorted(never - set(slugs)))
    for s in slugs:
        got = h.decide(B('engini tools call %s --args - --connection 7 --max-bytes 0' % s))
        asked = got in h.ASK_REASONS
        if got is not None and not asked:
            fails.append('snapshot slug %s: denied (only ask is expected)' % s)
        elif asked != (s in never):
            fails.append('snapshot slug %s: %s' % (s, 'asked' if asked else 'allowed'))
    if not quiet:
        for line in fails:
            print('FAIL ' + line)
        print('hook-selftest: %d rows, %d open-on-purpose, %d snapshot slugs, %d failures'
              % (len(ROWS), len(OPEN_ON_PURPOSE), len(slugs), len(fails)))
    return fails


if __name__ == '__main__':
    args = sys.argv[1:]
    hook = args[args.index('--hook') + 1] if '--hook' in args else os.path.join(ROOT, 'plugin/hooks/deny-never-verbs.py')
    sys.exit(1 if run(hook, '--quiet' in args) else 0)
