#!/usr/bin/env python3
"""Leak check against the PRIVATE term list: specific values known not to belong in a public repo. Not shipped.

  python3 tools/scrub-literals.py [--root DIR] [--env NAME] [--require] [--commits RANGE]

The terms are never in this repo: a public list of what must not leak would leak it. They come from an environment
variable (default SCRUB_DENYLIST, the repository secret of the same name), one term per line; blank lines are ignored.
A term matches as a case-sensitive substring, except that a term made only of digits must not touch another letter or
digit (so an id is not "found" inside a hash).

Scans the WHOLE tree - every tracked or new (not ignored) file, binary or not - and, with --commits, the author,
committer and message of every commit in RANGE (e.g. BASE..HEAD, or vX.Y.Z..HEAD). One exception: the rule lines of
tools/scrub-patterns.txt and tools/scrub-fixtures.txt are generic shapes and their made-up fixtures (each one is
mutation-tested), and a private list may share a generic word with them; their `#` comment lines ARE scanned.

On a hit it prints only WHERE (file:line, or commit + line) - never the term or the line, because CI logs of this
repo are public - and exits 1. Run it locally with the list in the variable to see the lines.

When the variable is missing or empty it prints a notice and exits 0 (pull requests from forks get no secrets);
with --require (the release) it fails instead.
"""
import os
import re
import subprocess
import sys


def arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def load_terms(raw):
    terms = []
    for line in raw.replace('\r', '').split('\n'):
        t = line.strip()
        if t:
            terms.append(t.encode('utf-8'))
    return terms


def matcher(terms):
    """One regex over bytes: digit-only terms need a non-alphanumeric neighbour, the rest are plain substrings."""
    parts = []
    for t in sorted(set(terms), key=len, reverse=True):
        rx = re.escape(t)
        if t.isdigit():
            rx = rb'(?<![0-9A-Za-z])' + rx + rb'(?![0-9A-Za-z])'
        parts.append(rx)
    return re.compile(b'|'.join(parts))


SHAPE_FILES = {'tools/scrub-patterns.txt', 'tools/scrub-fixtures.txt'}


def git(root, *args):
    return subprocess.run(['git'] + list(args), cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def tree_files(root):
    if os.path.exists(os.path.join(root, '.git')):
        p = git(root, 'ls-files', '-z', '-co', '--exclude-standard')
        if p.returncode:
            sys.exit('scrub-literals: git ls-files failed in %s' % root)
        names = p.stdout.decode('utf-8', 'replace').split('\0')
        return sorted(n for n in names if n and os.path.isfile(os.path.join(root, n)))
    found = []
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ('.git', '__pycache__')]
        found += [os.path.relpath(os.path.join(d, x), root).replace(os.sep, '/') for x in names]
    return sorted(found)


def commits(root, rng):
    p = git(root, 'log', '--format=%H', rng)
    if p.returncode:
        sys.exit('scrub-literals: git log %s failed: %s' % (rng, p.stderr.decode('utf-8', 'replace').strip()[:200]))
    for sha in p.stdout.decode().split():
        body = git(root, 'show', '-s', '--format=%an <%ae>%n%cn <%ce>%n%B', sha).stdout
        yield sha, body


def main(argv):
    root = os.path.abspath(arg(argv, '--root', os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    env = arg(argv, '--env', 'SCRUB_DENYLIST')
    rng = arg(argv, '--commits')
    terms = load_terms(os.environ.get(env, ''))
    if not terms:
        if '--require' in argv:
            print('::error::%s is not set or empty - the private term check cannot run, so nothing is released' % env)
            print('scrub-literals: FAIL - no term list')
            return 1
        print('::notice::%s is not available (a pull request from a fork gets no secrets, or the repository secret '
              'is not set) - the private term check is SKIPPED here. The push run on main and every release run it.'
              % env)
        print('scrub-literals: skipped (no term list)')
        return 0
    rx = matcher(terms)

    hits = []
    files = tree_files(root)
    for rel in files:
        with open(os.path.join(root, rel), 'rb') as f:
            for i, line in enumerate(f.read().split(b'\n'), 1):
                if rel in SHAPE_FILES and line.strip() and not line.startswith(b'#'):
                    continue  # a rule line: a generic shape or its fixture, never a real value
                if rx.search(line):
                    hits.append('%s:%d' % (rel, i))
    n_commits = 0
    if rng:
        for sha, body in commits(root, rng):
            n_commits += 1
            for i, line in enumerate(body.split(b'\n'), 1):
                if rx.search(line):
                    # line 1 is the author, line 2 the committer, line 3 on the message
                    hits.append('commit %s line %d' % (sha[:12], i))
    for h in hits:
        print(h)
    scope = '%d file(s)%s' % (len(files), ' and %d commit(s) in %s' % (n_commits, rng) if rng else '')
    if hits:
        print('scrub-literals: FAIL - %d line(s) above contain a term from the private list (terms are never printed;'
              ' run it locally with the list in %s to see them). Checked %s.' % (len(hits), env, scope))
        return 1
    print('scrub-literals: clean - %s checked against the private term list' % scope)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
