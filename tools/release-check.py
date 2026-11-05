#!/usr/bin/env python3
"""Release gate: installers get only TAGGED code while main moves. Not shipped.

  python3 tools/release-check.py [--root DIR] [--no-git]   the pin is sound (CI, every PR)
  python3 tools/release-check.py --release vX.Y.Z          also: vX.Y.Z may be released now (release workflow)
  python3 tools/release-check.py --bump vX.Y.Z --sha SHA   rewrite both pins to vX.Y.Z + SHA (release workflow only)

The pin:
- both marketplace manifests point the `skills` plugin at a `git-subdir` source of THIS repo, path `plugin`, with
  `ref` a release tag vX.Y.Z - never a branch, never a relative `./plugin` (that would serve whatever is on main) -
  and `sha` a full commit id. Both tools install `sha` when it is set (a name can be shadowed by a branch of the same
  name, a commit id cannot). The release commit cannot hold its own id, so `sha` is the gated commit the release
  commit sits on: same `plugin/` tree, one commit earlier;
- both manifests pin the same tag and the same sha, and the tag is not ahead of the plugin manifests' version;
- with git (default): the tag exists in this checkout, its plugin manifests carry the tag's own version, `sha` is the
  tagged commit or an ancestor of it with a byte-identical `plugin/` tree, and the remote `origin` has NO branch
  named v* (a branch named like the pinned tag is installed instead of the tag, by name). `--no-git` skips these
  (throwaway copies without history).
--release also checks: the tag is new, both plugin manifests carry exactly its version, it is ahead of the current
pin, and the working tree is clean.
"""
import json
import os
import re
import subprocess
import sys

REPO_URL = 'https://github.com/engini/skills.git'
PLUGIN = 'skills'
MARKETPLACES = {
    '.claude-plugin/marketplace.json': 'plugin',      # Claude Code: path as in its git-subdir reference
    '.agents/plugins/marketplace.json': './plugin',   # Codex: path as in its git-subdir reference
}
PLUGIN_MANIFESTS = ('plugin/.claude-plugin/plugin.json', 'plugin/.codex-plugin/plugin.json')
TAG = re.compile(r'^v([0-9]+)\.([0-9]+)\.([0-9]+)$')
SHA = re.compile(r'^[0-9a-f]{40}$')


def load(root, path):
    with open(os.path.join(root, path), encoding='utf-8') as f:
        return json.load(f)


def entry(doc):
    hits = [p for p in doc.get('plugins', []) if p.get('name') == PLUGIN]
    return hits[0] if len(hits) == 1 else None


def git(root, *args):
    p = subprocess.run(['git'] + list(args), cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return p.returncode, p.stdout.decode('utf-8', 'replace').strip()


def vtuple(tag):
    m = TAG.match(tag or '')
    return tuple(int(x) for x in m.groups()) if m else None


def check(root, use_git, release=None):
    fails = []
    versions = {}
    for mf in PLUGIN_MANIFESTS:
        versions[mf] = load(root, mf).get('version')
    if len(set(versions.values())) != 1:
        fails.append('plugin manifests disagree on version: %s' % versions)
    version = 'v%s' % versions[PLUGIN_MANIFESTS[0]]

    refs, shas = {}, {}
    for mf, want_path in MARKETPLACES.items():
        e = entry(load(root, mf))
        if e is None:
            fails.append('%s: expected exactly one plugin named %r' % (mf, PLUGIN))
            continue
        src = e.get('source')
        if not isinstance(src, dict) or src.get('source') != 'git-subdir':
            fails.append('%s: source must be a git-subdir pin, got %r' % (mf, src))
            continue
        if src.get('url') != REPO_URL:
            fails.append('%s: source url must be %s, got %r' % (mf, REPO_URL, src.get('url')))
        if src.get('path') != want_path:
            fails.append('%s: source path must be %r, got %r' % (mf, want_path, src.get('path')))
        extra = set(src) - {'source', 'url', 'path', 'ref', 'sha'}
        if extra:
            fails.append('%s: unexpected source keys %s' % (mf, sorted(extra)))
        ref = src.get('ref')
        if not vtuple(ref):
            fails.append('%s: ref must be a release tag vX.Y.Z, got %r' % (mf, ref))
        sha = src.get('sha')
        if not isinstance(sha, str) or not SHA.match(sha):
            fails.append('%s: sha must be a full 40-character lowercase commit id, got %r' % (mf, sha))
        refs[mf], shas[mf] = ref, sha
    if len(set(refs.values())) > 1:
        fails.append('the two marketplaces pin different tags: %s' % refs)
    if len(set(shas.values())) > 1:
        fails.append('the two marketplaces pin different commits: %s' % shas)
    pin = next(iter(refs.values()), None)
    pin_sha = next(iter(shas.values()), None)

    if vtuple(pin) and vtuple(version) and vtuple(pin) > vtuple(version):
        fails.append('pinned %s is ahead of the plugin version %s' % (pin, version))

    if use_git and vtuple(pin):
        rc, _ = git(root, 'rev-parse', '-q', '--verify', 'refs/tags/%s^{commit}' % pin)
        if rc:
            fails.append('pinned tag %s does not exist here (CI must fetch tags: fetch-depth 0)' % pin)
        else:
            for mf in PLUGIN_MANIFESTS:
                rc, out = git(root, 'show', '%s:%s' % (pin, mf))
                v = json.loads(out).get('version') if rc == 0 else None
                if 'v%s' % v != pin:
                    fails.append('tag %s: %s says version %r' % (pin, mf, v))
            if isinstance(pin_sha, str) and SHA.match(pin_sha):
                tagged = 'refs/tags/%s^{commit}' % pin
                if git(root, 'cat-file', '-e', '%s^{commit}' % pin_sha)[0]:
                    fails.append('pinned sha %s is not a commit here' % pin_sha)
                elif git(root, 'merge-base', '--is-ancestor', pin_sha, tagged)[0]:
                    fails.append('pinned sha %s is not tag %s or an ancestor of it' % (pin_sha, pin))
                elif git(root, 'diff', '--quiet', pin_sha, tagged, '--', 'plugin')[0]:
                    fails.append('plugin/ at pinned sha %s differs from plugin/ at tag %s' % (pin_sha, pin))
    if use_git:
        # A branch named like a release tag shadows it: `ref` is a name, and both git and the installers prefer
        # refs/heads/<name>. A ruleset blocks creating refs/heads/v*; this is the second lock.
        rc, out = git(root, 'ls-remote', '--heads', 'origin', 'refs/heads/v*')
        if rc:
            fails.append('cannot list the branches of remote origin (needed to prove no branch shadows a release tag)')
        else:
            names = [ln.split('\t', 1)[1] for ln in out.splitlines() if '\t' in ln]
            if names:
                fails.append('remote origin has branch(es) named v*, which shadow release tags of the same name: %s'
                             % ', '.join(names))

    if release is not None:
        if not vtuple(release):
            fails.append('release tag must be vX.Y.Z, got %r' % release)
        elif release != version:
            fails.append('release %s does not equal the plugin manifests version %s' % (release, version))
        elif vtuple(pin) and vtuple(release) <= vtuple(pin):
            fails.append('release %s is not ahead of the current pin %s' % (release, pin))
        if use_git:
            rc, _ = git(root, 'rev-parse', '-q', '--verify', 'refs/tags/%s' % release)
            if rc == 0:
                fails.append('tag %s already exists' % release)
            rc, out = git(root, 'status', '--porcelain')
            if rc or out:
                fails.append('working tree is not clean')
    return fails


def bump(root, tag, sha):
    if not vtuple(tag):
        sys.exit('release-check: --bump wants vX.Y.Z')
    if not SHA.match(sha or ''):
        sys.exit('release-check: --bump wants --sha with a full 40-character lowercase commit id')
    for mf in MARKETPLACES:
        p = os.path.join(root, mf)
        doc = load(root, mf)
        entry(doc)['source']['ref'] = tag
        entry(doc)['source']['sha'] = sha
        with open(p, 'w', encoding='utf-8') as f:
            f.write(json.dumps(doc, indent=2) + '\n')
    print('release-check: both marketplaces now pin %s at %s' % (tag, sha))


def main(argv):
    root = argv[argv.index('--root') + 1] if '--root' in argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if '--bump' in argv:
        bump(root, argv[argv.index('--bump') + 1], argv[argv.index('--sha') + 1] if '--sha' in argv else None)
        return 0
    release = argv[argv.index('--release') + 1] if '--release' in argv else None
    fails = check(root, '--no-git' not in argv, release)
    for f in fails:
        print('FAIL ' + f)
    print('release-check: %s' % ('FAIL' if fails else 'ok'))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
