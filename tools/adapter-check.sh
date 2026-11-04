#!/usr/bin/env bash
# The adapters stay thin pointers. Each adapter, with only its `name` and `description` removed, must hash
# to the template hash in tools/adapter-templates.sha256 - so a paraphrased or condensed rule in an adapter fails
# even when it "says the same thing". Also: exactly one build-engini-workflow skill directory, no symlinks.
#   tools/adapter-check.sh [repo root]     --print  prints the current hashes (to update the template file in a reviewed PR)
set -u
root=${1:-$(cd "$(dirname "$0")/.." && pwd)}
[ "$root" = "--print" ] && root=$(cd "$(dirname "$0")/.." && pwd)
python3 - "$root" "$*" <<'PY'
import hashlib, os, re, sys
root, args = sys.argv[1], sys.argv[2]
fails = []

def body_md(text):
    # drop `name:` and the folded `description:` block from the YAML frontmatter
    out, skip = [], False
    for line in text.split('\n'):
        if skip and (line.startswith('  ') or line == ''):
            continue
        skip = False
        if line.startswith('name:'):
            continue
        if line.startswith('description:'):
            skip = True
            continue
        out.append(line)
    return '\n'.join(out)

def body_toml(text):
    text = re.sub(r'(?m)^name = .*\n', '', text)
    return re.sub(r'(?s)description = """.*?"""\n', '', text)

adapters = {'plugin/agents/flo.md': body_md, 'plugin/.codex/agents/flo.toml': body_toml}
current = {}
for path, fn in adapters.items():
    with open(os.path.join(root, path), encoding='utf-8') as f:
        current[path] = hashlib.sha256(fn(f.read()).encode('utf-8')).hexdigest()
if '--print' in args:
    for p, h in current.items():
        print('%s  %s' % (h, p))
    sys.exit(0)
want = {}
with open(os.path.join(root, 'tools/adapter-templates.sha256'), encoding='utf-8') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            h, p = line.split()
            want[p] = h
for p, h in current.items():
    if want.get(p) != h:
        fails.append('%s: body differs from its template (only name/description may vary)' % p)
skills = [d for d, _, _ in os.walk(os.path.join(root, 'plugin')) if os.path.basename(d) == 'build-engini-workflow']
if len(skills) != 1:
    fails.append('expected exactly one build-engini-workflow directory, found %d' % len(skills))
for d, dirs, files in os.walk(os.path.join(root, 'plugin')):
    for n in dirs + files:
        if os.path.islink(os.path.join(d, n)):
            fails.append('symlink in the payload: %s' % os.path.relpath(os.path.join(d, n), root))
for x in fails:
    print('FAIL ' + x)
print('adapter-check: %s' % ('FAIL' if fails else 'ok'))
sys.exit(1 if fails else 0)
PY
