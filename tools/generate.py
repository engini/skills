#!/usr/bin/env python3
"""Emit every generated copy of the Flo rules from tools/rules.json.

  python3 tools/generate.py           rewrite the generated blocks in place
  python3 tools/generate.py --check   exit 1 and name each stale file (CI)

Generated blocks: the hook's constant block, the SKILL.md never-verb block, and the plugin README never list and settings block.
"""
import json
import os

import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = 'plugin/hooks/deny-never-verbs.py'
SKILL = 'plugin/skills/build-engini-workflow/SKILL.md'
README = 'plugin/README.md'


def load_rules(root=ROOT):
    with open(os.path.join(root, 'tools/rules.json'), encoding='utf-8') as f:
        return json.load(f)


def hook_block(r):
    lines = [
        'DENY_TOKEN = %r' % r['deny_token'],
        'ASK_TOKEN = %r' % r['ask_token'],
        'NEVER_VERBS = frozenset(%r)' % sorted(r['never_verbs']),
        'CALL_VALUE_FLAGS = frozenset(%r)' % sorted(r['call_value_flags']),
        'RAW_KEY_COMMANDS = %r' % (tuple(sorted(tuple(c) for c in r['raw_key_commands'])),),
        'RAW_KEY_FLAGS = %r' % (tuple(r['raw_key_flags']),),
        'KEY_ENV = %r' % ('(?:' + '|'.join(r['key_env_vars']) + ')'),
        'KEY_PATH = %r' % (tuple(r['key_path_patterns']),),
        'SELF_PROTECT = %r' % (tuple(r['self_protect_patterns']),),
    ]
    return '\n'.join(lines) + '\n'


def skill_block(r):
    return ('<!-- generated from the rules source - do not edit by hand -->\n```text\n'
            + '\n'.join(r['never_verbs']) + '\n```\n')


def readme_block(r):
    calls = ['Bash(engini tools call %s:*)' % s for s in r['never_verbs']]
    raw = ['Bash(engini %s:*)' % ' '.join(c) for c in r['raw_key_commands']] + ['Bash(engini login --api-key:*)']
    # ask, not deny: the user is asked every time. (With the hook installed it still refuses the raw-key commands
    # when the agent runs them, and tells the agent to hand them to the user.)
    ask = ['Bash(engini tools call %s:*)' % s for s in r['write_verbs_ask']] + calls + raw
    deny = [
        'Read(~/.config/engini/**)',
        'Read(~/AppData/Roaming/engini/**)',
        'Read(~/engini/config.toml)',
        'Bash(cat ~/.config/engini/config.toml)',
        'Bash(printenv:*)',
        'Bash(env)',
    ]
    settings = {'permissions': {'allow': ['Bash(engini:*)'], 'ask': ask, 'deny': deny}}
    rules = ['# Flo: a prompt before every write, before the four never-verbs and before the raw-key commands (decline those and run them yourself).']
    for s in r['write_verbs_ask']:
        rules.append('prefix_rule(pattern = ["engini", "tools", "call", "%s"], decision = "prompt")' % s)
    for s in r['never_verbs']:
        rules.append('prefix_rule(pattern = ["engini", "tools", "call", "%s"], decision = "prompt", '
                     'justification = "Flo calls this only when you asked for exactly this action on this workflow")' % s)
    for c in r['raw_key_commands']:
        rules.append('prefix_rule(pattern = %s, decision = "prompt", '
                     'justification = "takes or stores a raw API key - decline this, run it in your own terminal outside Codex, never paste the key into the chat")'
                     % json.dumps(['engini'] + list(c)))
    return ('<!-- generated from the rules source - do not edit by hand -->\n'
            '**Claude Code** - merge into your user settings (`settings.json` in your `~/.claude` folder):\n\n'
            '```json\n' + json.dumps(settings, indent=2) + '\n```\n\n'
            '**Codex** - save as `~/.codex/rules/flo.rules`:\n\n'
            '```python\n' + '\n'.join(rules) + '\n```\n')


def readme_list(r):
    return '<!-- generated from the rules source - do not edit by hand -->\n' + ''.join('- `%s`\n' % v for v in r['never_verbs'])


TARGETS = [
    (HOOK, '# BEGIN GENERATED from tools/rules.json by tools/generate.py - do not edit by hand\n',
     '# END GENERATED\n', hook_block),
    (SKILL, '<!-- flo:never-verbs:begin -->\n', '<!-- flo:never-verbs:end -->\n', skill_block),
    (README, '<!-- flo:deny-block:begin -->\n', '<!-- flo:deny-block:end -->\n', readme_block),
    (README, '<!-- flo:never-list:begin -->\n', '<!-- flo:never-list:end -->\n', readme_list),
]


def render(root=ROOT):
    """{path: (current text, expected text)}"""
    r = load_rules(root)
    out = {}
    for path, begin, end, fn in TARGETS:
        if path not in out:
            with open(os.path.join(root, path), encoding='utf-8') as f:
                text = f.read()
            out[path] = (text, text)
        cur, want = out[path]
        if want.count(begin) != 1 or want.count(end) != 1:
            raise SystemExit('%s: expected exactly one %r and one %r marker' % (path, begin.strip(), end.strip()))
        head, rest = want.split(begin)
        _, tail = rest.split(end)
        out[path] = (cur, head + begin + fn(r) + end + tail)
    return out


def main(argv):
    root = argv[argv.index('--root') + 1] if '--root' in argv else ROOT
    stale = []
    for path, (cur, want) in render(root).items():
        if cur != want:
            stale.append(path)
            if '--check' not in argv:
                with open(os.path.join(root, path), 'w', encoding='utf-8') as f:
                    f.write(want)
    if '--check' in argv and stale:
        print('generate: stale generated blocks (run python3 tools/generate.py): ' + ', '.join(stale))
        return 1
    print('generate: %s' % ('rewrote ' + ', '.join(stale) if stale and '--check' not in argv else 'all generated blocks current'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
