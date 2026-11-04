#!/usr/bin/env python3
"""Doc gates. Not shipped.

  python3 tools/rules-check.py [--root DIR]

- every generated block is current (tools/generate.py --check);
- the SKILL.md never-verb block sits in the BODY (past the closing ---) and lists exactly tools/rules.json's four;
- the README settings block asks (never denies) for all four never-verbs and for every raw-key command, keeps the
  key-read rules as deny (Claude settings JSON parsed), and the Codex rules prompt (never forbid) for the four and
  for the raw-key commands, whose justification tells the user to decline and run them in their own terminal
  (Codex has no hook, so these rules are its only layer there);
- tool-map.md section 2 and agent-rules.md still name each never-verb, and say Flo calls it only when the user asks;
- SKILL.md and agent-rules.md tell Flo to hand key-handling commands to the user's own terminal, never to `!`;
- every HTTP refusal in tool-map.md section 3a has its own TROUBLESHOOTING.md row, matched on the exact
  `status code` pair with word boundaries (a bare NOT_FOUND grep is satisfied by SLUG_NOT_FOUND).
"""
import json
import os
import re
import subprocess
import sys

SKILL_DIR = 'plugin/skills/build-engini-workflow'


def read(root, path):
    with open(os.path.join(root, path), encoding='utf-8') as f:
        return f.read()


def block(text, begin, end):
    if text.count(begin) != 1 or text.count(end) != 1:
        return None
    return text.split(begin)[1].split(end)[0]


def main(argv):
    root = argv[argv.index('--root') + 1] if '--root' in argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fails = []
    gen = subprocess.run([sys.executable, os.path.join(root, 'tools/generate.py'), '--check', '--root', root],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if gen.returncode:
        fails.append(gen.stdout.decode().strip())
    never = json.loads(read(root, 'tools/rules.json'))['never_verbs']

    skill = read(root, SKILL_DIR + '/SKILL.md')
    parts = skill.split('\n---\n', 1)
    if not skill.startswith('---\n') or len(parts) != 2:
        fails.append('SKILL.md: no closing frontmatter ---')
    else:
        body = parts[1]
        b = block(body, '<!-- flo:never-verbs:begin -->', '<!-- flo:never-verbs:end -->')
        listed = re.findall(r'^engini_workflows_[a-z_]+$', b or '', re.M)
        if listed != never:
            fails.append('SKILL.md body never-verb block lists %s, rules.json has %s' % (listed, never))
        if 'flo:never-verbs' in parts[0]:
            fails.append('SKILL.md: never-verb block marker found in the frontmatter')

    rules = json.loads(read(root, 'tools/rules.json'))
    raw = ['Bash(engini %s:*)' % ' '.join(c) for c in rules['raw_key_commands']] + ['Bash(engini login --api-key:*)']
    readme = read(root, 'plugin/README.md')
    b = block(readme, '<!-- flo:deny-block:begin -->', '<!-- flo:deny-block:end -->') or ''
    m = re.search(r'```json\n(.*?)\n```', b, re.S)
    try:
        perms = json.loads(m.group(1))['permissions'] if m else {}
    except Exception:
        perms = {}
    ask, deny = perms.get('ask', []), perms.get('deny', [])
    m = re.search(r'```python\n(.*?)\n```', b, re.S)
    codex = m.group(1) if m else ''
    for s in never:
        rule = 'Bash(engini tools call %s:*)' % s
        if rule not in ask:
            fails.append('README settings block: Claude snippet does not ask for %s' % s)
        if rule in deny:
            fails.append('README settings block: Claude snippet denies %s (it must ask)' % s)
        if '["engini", "tools", "call", "%s"], decision = "prompt"' % s not in codex:
            fails.append('README settings block: Codex rules do not prompt for %s' % s)
        if '["engini", "tools", "call", "%s"], decision = "forbidden"' % s in codex:
            fails.append('README settings block: Codex rules forbid %s (it must prompt)' % s)
    for rule in raw:
        if rule not in ask:
            fails.append('README settings block: Claude snippet does not ask for %s' % rule)
        if rule in deny:
            fails.append('README settings block: Claude snippet denies %s (it must ask)' % rule)
    for c in rules['raw_key_commands']:
        line = [ln for ln in codex.split('\n') if ln.startswith('prefix_rule(pattern = %s,' % json.dumps(['engini'] + list(c)))]
        if not line or 'decision = "prompt"' not in line[0]:
            fails.append('README settings block: Codex rules do not prompt for engini %s' % ' '.join(c))
        elif 'own terminal outside Codex' not in line[0] or 'never paste the key' not in line[0]:
            fails.append('README settings block: Codex justification for engini %s must say to decline, use your own terminal '
                         'and never paste the key' % ' '.join(c))
    if 'decision = "forbidden"' in codex:
        fails.append('README settings block: Codex rules use "forbidden" (every Flo rule there must prompt)')
    for rule in ('Read(~/.config/engini/**)', 'Read(~/AppData/Roaming/engini/**)', 'Read(~/engini/config.toml)',
                 'Bash(cat ~/.config/engini/config.toml)', 'Bash(printenv:*)', 'Bash(env)'):
        if rule not in deny:
            fails.append('README settings block: Claude snippet no longer denies %s' % rule)

    tool_map = read(root, SKILL_DIR + '/references/tool-map.md')
    sec2 = tool_map.split('## 2.', 1)[-1].split('\n## 3.', 1)[0]
    for s in never:
        if not [ln for ln in sec2.split('\n') if s in ln and 'ONLY IF THE USER ASKS' in ln]:
            fails.append('tool-map.md section 2: no "ONLY IF THE USER ASKS" row for %s' % s)
    rules_md = read(root, SKILL_DIR + '/references/agent-rules.md')
    for s in never:
        if s not in rules_md:
            fails.append('agent-rules.md: %s not named' % s)
    for path, text in (('SKILL.md', skill), ('agent-rules.md', rules_md)):
        if 'own terminal' not in text or 'not with `!`' not in text:
            fails.append('%s: no "own terminal" / "not with `!`" instruction for key-handling commands' % path)
        if 'only when the user explicitly asks' not in text:
            fails.append('%s: no "only when the user explicitly asks" rule for the never-verbs' % path)

    sec3a = tool_map.split('### 3a.', 1)[-1].split('### 3b.', 1)[0]
    codes = re.findall(r'^\| (\d{3}) `([A-Z_]+)` \|', sec3a, re.M)
    if len(codes) != 15:
        fails.append('tool-map.md 3a: expected 15 HTTP refusal rows, found %d' % len(codes))
    trouble = read(root, 'plugin/TROUBLESHOOTING.md')
    rows = [ln for ln in trouble.split('\n') if ln.startswith('|')]
    for status, code in codes:
        pat = re.compile(r'(?<![A-Z_])%s(?![A-Z_]).*?\b%s\b|\b%s\b.*?(?<![A-Z_])%s(?![A-Z_])' % (code, status, status, code))
        if not [r for r in rows if pat.search(r)]:
            fails.append('TROUBLESHOOTING.md: no row for %s %s' % (status, code))

    for x in fails:
        print('FAIL ' + x)
    print('rules-check: %s' % ('FAIL' if fails else 'ok'))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
