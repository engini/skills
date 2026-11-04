#!/usr/bin/env python3
"""Server-contract check. Read-only: `engini tools list` + `engini tools get` only, never `tools call`.

  python3 tools/contract-check.py            diff the live engini_workflows tools against tools/contract/snapshot.json
  python3 tools/contract-check.py --update   rewrite the snapshot from the live server (commit it in a reviewed PR)

Fails (exit 1) only when a never-verb from tools/rules.json is missing from the live set: a renamed never-verb means
the hook silently stops matching while every document still says the verb is refused. New, removed or changed
slugs outside the four are reported for information only (they already run on every customer's machine).
Credentials: the CLI's own login, or ENGINI_API_KEY in CI (a read-only, workspace-scoped key). Nothing is written to
any tenant.
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(ROOT, 'tools/contract/snapshot.json')
APP = 'engini_workflows'


def cli(*args):
    out = subprocess.run(['engini'] + list(args), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return json.loads(out.stdout.decode('utf-8'))


def live():
    tools = {}
    for t in cli('tools', 'list', '--application', APP, '--json'):
        slug = t['tool_slug']
        detail = cli('tools', 'get', slug, '--json')
        schema = detail.get('input_schema') or {}
        tools[slug] = {
            'description': detail.get('description'),
            'is_deprecated': detail.get('is_deprecated'),
            'required': sorted(schema.get('required') or []),
            'properties': sorted((schema.get('properties') or {}).keys()),
            'schema_sha256': hashlib.sha256(json.dumps(schema, sort_keys=True).encode('utf-8')).hexdigest(),
        }
    return tools


def main(argv):
    with open(os.path.join(ROOT, 'tools/rules.json'), encoding='utf-8') as f:
        never = json.load(f)['never_verbs']
    now = live()
    if '--update' in argv:
        os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
        with open(SNAPSHOT, 'w', encoding='utf-8') as f:
            json.dump({'application': APP, 'tools': now}, f, indent=2, sort_keys=True)
            f.write('\n')
        print('contract-check: snapshot updated, %d tools' % len(now))
    with open(SNAPSHOT, encoding='utf-8') as f:
        snap = json.load(f)['tools']
    missing_never = [s for s in never if s not in now]
    for s in sorted(set(now) - set(snap)):
        print('info: new slug %s (allowed by the hook - only the four never-verbs ask)' % s)
    for s in sorted(set(snap) - set(now)):
        print('info: slug gone from the server: %s' % s)
    for s in sorted(set(now) & set(snap)):
        if now[s] != snap[s]:
            changed = [k for k in now[s] if now[s][k] != snap[s].get(k)]
            print('info: %s changed: %s' % (s, ', '.join(changed)))
    if missing_never:
        print('FAIL: never-verb(s) missing or renamed on the server: %s. The hook no longer matches them; update '
              'tools/rules.json, regenerate, re-run the self-test and release.' % ', '.join(missing_never))
        return 1
    print('contract-check: %d live tools, all %d never-verbs present' % (len(now), len(never)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
