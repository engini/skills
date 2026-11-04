#!/usr/bin/env bash
# Leak check for a PUBLIC repo: nothing internal lands here, in the plugin or in the tooling.
#   tools/scrub-check.sh [repo root]                   exit 1 and print each hit
#   tools/scrub-check.sh [repo root] --commits RANGE   ALSO the author, committer and message of each commit in RANGE
#
# Scans the WHOLE repo: every tracked or new (not ignored) file when the root is a git checkout, every file under it
# otherwise. Rows come from tools/scrub-patterns.txt, one Python regex per row, each with a scope:
#   repo     every file
#   payload  plugin/ only (stricter rules that the tooling itself cannot meet, e.g. it names `.claude/` paths)
# The rows are GENERIC shapes (internal host names, long numeric ids, ticket refs, class-name families, key-shaped
# values ...), never a list of real values: a list of what must not leak would itself leak it.
# Skipped: tools/scrub-patterns.txt and tools/scrub-fixtures.txt (they hold the shapes), .git/, binary files.
# Commits (--commits): only `repo` rows, and GitHub / Claude no-reply identities are not email hits. The specific
# values known not to belong here are a PRIVATE list, checked by tools/scrub-literals.py.
set -u
root=$(cd "$(dirname "$0")/.." && pwd)
if [ $# -gt 0 ] && [ "$1" != --commits ]; then root=$1; shift; fi
python3 -I - "$root" "$@" <<'PY'
import os, re, subprocess, sys

root = os.path.abspath(sys.argv[1])
rng = sys.argv[sys.argv.index('--commits') + 1] if '--commits' in sys.argv[2:] else None
SKIP = {'tools/scrub-patterns.txt', 'tools/scrub-fixtures.txt'}

rows = []
with open(os.path.join(root, 'tools/scrub-patterns.txt'), encoding='utf-8') as f:
    for n, line in enumerate(f, 1):
        line = line.rstrip('\n')
        if not line.strip() or line.startswith('#'):
            continue
        scope, _, rx = line.partition(' ')
        rx = rx.strip()
        if scope not in ('repo', 'payload') or not rx:
            sys.exit('scrub-check: tools/scrub-patterns.txt:%d: want "repo <regex>" or "payload <regex>"' % n)
        rows.append((n, scope, re.compile(rx)))
if not rows:
    sys.exit('scrub-check: no rows in tools/scrub-patterns.txt')


def files():
    if os.path.isdir(os.path.join(root, '.git')):
        out = subprocess.run(['git', 'ls-files', '-z', '-co', '--exclude-standard'], cwd=root,
                             stdout=subprocess.PIPE, check=True).stdout.decode('utf-8')
        return sorted(p for p in out.split('\0') if p and os.path.isfile(os.path.join(root, p)))
    found = []
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ('.git', '__pycache__')]
        found += [os.path.relpath(os.path.join(d, x), root).replace(os.sep, '/') for x in names]
    return sorted(found)


hits = 0
for rel in files():
    if rel in SKIP:
        continue
    with open(os.path.join(root, rel), 'rb') as f:
        raw = f.read()
    if b'\0' in raw:
        continue
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        continue
    payload = rel.startswith('plugin/')
    for i, line in enumerate(text.split('\n'), 1):
        for n, scope, rx in rows:
            if scope == 'payload' and not payload:
                continue
            m = rx.search(line)
            if m:
                hits += 1
                print('%s:%d: [row %d %s] %r in: %s' % (rel, i, n, scope, m.group(0), line.strip()[:160]))
# identities GitHub and Claude Code put on commits: public no-reply addresses, not a staff or customer address
NOREPLY = re.compile(r'(?:\b[0-9]+\+)?[A-Za-z0-9-]+(?:\[bot\])?@users\.noreply\.github\.com\b|\bnoreply@(?:github|anthropic)\.com\b')
if rng:
    p = subprocess.run(['git', 'log', '--format=%H', rng], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        sys.exit('scrub-check: git log %s failed: %s' % (rng, p.stderr.decode('utf-8', 'replace').strip()[:200]))
    shas = p.stdout.decode().split()
    for sha in shas:
        body = subprocess.run(['git', 'show', '-s', '--format=%an <%ae>%n%cn <%ce>%n%B', sha], cwd=root,
                              stdout=subprocess.PIPE, check=True).stdout.decode('utf-8', 'replace')
        for i, line in enumerate(body.split('\n'), 1):
            line = NOREPLY.sub('noreply@example.com', line)
            for n, scope, rx in rows:
                if scope != 'repo':
                    continue
                m = rx.search(line)
                if m:
                    hits += 1
                    print('commit %s line %d: [row %d] %r in: %s' % (sha[:12], i, n, m.group(0), line.strip()[:160]))
    print('scrub-check: %d commit(s) in %s checked' % (len(shas), rng))
if hits:
    print('scrub-check: FAIL - %d hit(s) in %s (lines above)' % (hits, root))
    sys.exit(1)
print('scrub-check: clean (%s)' % root)
PY
