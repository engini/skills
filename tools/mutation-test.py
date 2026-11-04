#!/usr/bin/env python3
"""Prove every gate can go red: hook, rules, adapters, scrub and the release pin. Not shipped.

  python3 tools/mutation-test.py

Each mutation is applied to a throwaway copy of the repo and must make its gate FAIL. A mutation whose anchor text
is gone fails loudly too, so a refactor cannot silently retire one.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # importing the hook must not drop a __pycache__ into the payload
HOOK = 'plugin/hooks/deny-never-verbs.py'

spec = importlib.util.spec_from_file_location('selftest', os.path.join(ROOT, 'tools/hook-selftest.py'))
selftest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selftest)

HOOK_MUTATIONS = [
    ('9a-1 drop a never-verb from the generated constant',
     "'engini_workflows_rerun_execution', ", ''),
    ('9a-2 delete family 1b',
     'for judge in (judge_call, judge_named, judge_raw_key, judge_env_dump):',
     'for judge in (judge_call, judge_raw_key, judge_env_dump):'),
    ('9a-3 check only the token right after call',
     'for tok in candidates(seg, i + 1):', 'for tok in seg[i + 2:i + 3]:'),
    ('9a-4 metacharacter blacklist instead of the slug shape test',
     'if not SLUG_SHAPE.match(tok):', "if re.search(r'[$`(]', tok):"),
    ('9a-5 exemption widened to "the segment mentions tools get"',
     "exempt = not has_call and j >= 2 and seg[j - 2].lower() == 'tools' and seg[j - 1].lower() == 'get'",
     "exempt = 'tools' in [t.lower() for t in seg] and 'get' in [t.lower() for t in seg]"),
    ('9a-6 a sub-shell opener terminates its segment',
     '            j = _close(text, i)\n            word.append(text[i:j + 1])\n            inner(text[i + 1:j])\n            i = j + 1\n',
     '            end_word()\n            if seg:\n                out.append(seg)\n                seg = []\n            i += 1\n'),
    ('9a-7 heredoc strip trusts any reader (consumer anchor dropped)',
     'return (_cli_invocation(seg[:k]) and args_stdin', 'return (args_stdin'),
    ('9a-8 continuations joined before the heredoc strip',
     "    text = cmd if ps else strip_flo_heredoc(cmd)\n    text = text.replace('`\\n' if ps else '\\\\\\n', '')\n",
     "    text = cmd.replace('`\\n' if ps else '\\\\\\n', '')\n    text = text if ps else strip_flo_heredoc(text)\n"),
    ('9a-9 Grep path and glob judged side by side, no ancestor check',
     "or (path and KEY_ANCESTOR.match(_norm(path)))", "or False"),
    ('9a-10 no `.`/`..` segment rule under .claude/.codex',
     r"\\.\\.?(?=[", r"\\.\\.?XQ(?=["),
    ('9a-11 no rule for cd into a .claude/.codex subfolder',
     '(?:cd|pushd|chdir|Set-Location', '(?:cdXQ|pushdXQ|chdirXQ|Set-LocationXQ'),
    ('9a-12 file tools judged on the literal path only',
     'if tool in WRITE_TOOLS and any(SELF_RE.search(f) for f in forms):', 'if tool in WRITE_TOOLS and SELF_RE.search(path):'),
    ('9a-13 Grep/Glob path not resolved against cwd',
     "if any(_reaches_key(r) for r in _reals(path or '.', cwd)):", 'if False:'),
    ('9a-14 any npx @engini/cli@<spec> owns the heredoc',
     "words[0] == 'npx' and NPX_CLI.match(words[1]) is not None", "words[0] == 'npx' and _is_cli(words[1])"),
    # ask vs deny is its own outcome
    ('9a-15 the hook output always says deny',
     "'permissionDecision': 'ask' if reason in ASK_REASONS else 'deny'", "'permissionDecision': 'deny'"),
    ('9a-16 the first reason wins (a later refusal no longer beats a question)',
     "            if reason in ASK_REASONS:\n                ask = ask or reason   # keep looking: a refusal in a later segment beats a question\n            elif reason:\n                return reason\n",
     "            if reason:\n                return reason\n"),
    ('9a-17 never-verbs go back to deny',
     'ASK_REASONS = frozenset((R_NEVER, R_UNREADABLE))', 'ASK_REASONS = frozenset((R_UNREADABLE,))'),
    ('9a-18 unreadable slugs go back to deny',
     'ASK_REASONS = frozenset((R_NEVER, R_UNREADABLE))', 'ASK_REASONS = frozenset((R_NEVER,))'),
    ('9a-19 raw-key commands become a question',
     'ASK_REASONS = frozenset((R_NEVER, R_UNREADABLE))', 'ASK_REASONS = frozenset((R_NEVER, R_UNREADABLE, R_RAW_KEY))'),
    ('9a-20 the raw-key refusal sends the user to ! instead of their own terminal',
     "- not with the ! prefix: in Claude Code's ! mode the input is not a terminal, so the CLI cannot hide the key.",
     "- run it with the ! prefix, for example ! engini login."),
    ('9a-21 the raw-key refusal loses the own-terminal instruction',
     "Stop and tell the user to run the command in their OWN terminal, outside Claude Code and Codex", "Stop and tell the user to run the command"),
    ('9a-22 the raw-key refusal suggests --api-key',
     "Give the exact command with no key in it (for example: engini login, or", "Give the exact command (for example: engini login --api-key <key>, or"),
]


def copy_repo():
    d = tempfile.mkdtemp(prefix='flo-mut-')
    for sub in ('plugin', 'tools', '.claude-plugin', '.agents'):
        shutil.copytree(os.path.join(ROOT, sub), os.path.join(d, sub))
    return d


def edit(root, path, old, new, count=1):
    p = os.path.join(root, path)
    with open(p, encoding='utf-8') as f:
        s = f.read()
    if s.count(old) < 1:
        raise SystemExit('mutation anchor not found in %s: %r' % (path, old[:60]))
    with open(p, 'w', encoding='utf-8') as f:
        f.write(s.replace(old, new, count))


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).returncode


def main():
    survived = []
    # --- hook mutations against the self-test
    for name, old, new in HOOK_MUTATIONS:
        d = copy_repo()
        edit(d, HOOK, old, new)
        fails = selftest.run(os.path.join(d, HOOK), quiet=True)
        caught = [f for f in fails if not f.startswith('snapshot')]
        print('%s %s -> caught by: %s' % ('RED ' if fails else 'SURVIVED', name,
                                           '; '.join(re.sub(r'\s+', ' ', f.split(' -> ')[0])[:70] for f in (caught or fails)[:4])))
        if not fails:
            survived.append(name)
        shutil.rmtree(d)

    # --- generator / prose / adapter mutations
    never = json.load(open(os.path.join(ROOT, 'tools/rules.json')))['never_verbs']
    skill = 'plugin/skills/build-engini-workflow/SKILL.md'

    def m_paraphrase(d):
        edit(d, 'plugin/.codex/agents/flo.toml', 'The rules live in the skill, not here.',
             'The rules live in the skill, not here. Never delete or run a workflow.')

    def m_second_skill(d):
        shutil.copytree(os.path.join(d, 'plugin/skills/build-engini-workflow'),
                        os.path.join(d, 'plugin/agents/build-engini-workflow'))

    def m_drop_from_skill(d):
        edit(d, skill, never[0] + '\n', '')

    def m_frontmatter_only(d):
        p = os.path.join(d, skill)
        s = open(p, encoding='utf-8').read()
        blk = re.search(r'<!-- flo:never-verbs:begin -->.*?<!-- flo:never-verbs:end -->\n', s, re.S).group(0)
        s = s.replace(blk, '').replace('\ndescription: ', '\ndescription: Never: %s. ' % ', '.join(never), 1)
        open(p, 'w', encoding='utf-8').write(s)

    def m_readme_emptied(d):
        p = os.path.join(d, 'plugin/README.md')
        s = open(p, encoding='utf-8').read()
        s = re.sub(r'(<!-- flo:deny-block:begin -->\n).*?(<!-- flo:deny-block:end -->)', r'\1\2', s, flags=re.S)
        open(p, 'w', encoding='utf-8').write(s)

    def m_hook_constant(d):
        edit(d, HOOK, "'engini_workflows_run_workflow'", "'engini_workflows_run_workflows'")

    def m_rules_json(d):
        p = os.path.join(d, 'tools/rules.json')
        r = json.load(open(p))
        r['never_verbs'] = r['never_verbs'][:-1]
        json.dump(r, open(p, 'w'), indent=2)

    def m_trouble_row(d):
        p = os.path.join(d, 'plugin/TROUBLESHOOTING.md')
        s = open(p, encoding='utf-8').read()
        s = '\n'.join(ln for ln in s.split('\n') if '404 `NOT_FOUND`' not in ln)
        open(p, 'w', encoding='utf-8').write(s)

    def regen(d):
        subprocess.run([sys.executable, 'tools/generate.py'], cwd=d, stdout=subprocess.DEVNULL, check=True)

    def m_gen_verbs_deny(d):
        # the generator itself drifts (blocks stay "current"): the four never-verbs land in deny, not ask
        edit(d, 'tools/generate.py', "ask = ['Bash(engini tools call %s:*)' % s for s in r['write_verbs_ask']] + calls + raw",
             "ask = ['Bash(engini tools call %s:*)' % s for s in r['write_verbs_ask']] + raw")
        edit(d, 'tools/generate.py', "    deny = [\n", "    deny = calls + [\n")
        regen(d)

    def m_gen_raw_deny(d):
        edit(d, 'tools/generate.py', "] + calls + raw\n", "] + calls\n")
        edit(d, 'tools/generate.py', "    deny = [\n", "    deny = raw + [\n")
        regen(d)

    def m_gen_codex_raw_forbid(d):
        # the old behaviour: Codex forbids the raw-key commands instead of asking
        edit(d, 'tools/generate.py', 'pattern = %s, decision = "prompt", \'', 'pattern = %s, decision = "forbidden", \'')
        regen(d)

    def m_gen_codex_justification(d):
        # Codex asks but no longer tells the user to decline and keep the key out of the chat
        edit(d, 'tools/generate.py', ', never paste the key into the chat', '')
        regen(d)

    def m_prose_bang(d):
        edit(d, 'plugin/skills/build-engini-workflow/SKILL.md', 'not with `!`', 'with `!` is fine')

    def m_prose_unasked(d):
        edit(d, 'plugin/skills/build-engini-workflow/references/agent-rules.md', 'only when the user explicitly asks', 'whenever it helps')

    def m_toolmap_never(d):
        edit(d, 'plugin/skills/build-engini-workflow/references/tool-map.md', '**ONLY IF THE USER ASKS** (same rule) |\n| `engini_workflows_delete_workflow`',
             '**NEVER** |\n| `engini_workflows_delete_workflow`')

    gates = {'rules': [sys.executable, 'tools/rules-check.py'], 'adapter': ['bash', 'tools/adapter-check.sh']}
    for name, fn, gate in [
        ('11-1 paraphrased rule in flo.toml', m_paraphrase, 'adapter'),
        ('11-2 second copy of the skill dir', m_second_skill, 'adapter'),
        ('11-3 never-verb dropped from the SKILL.md block', m_drop_from_skill, 'rules'),
        ('11-4 never-verbs moved into frontmatter only', m_frontmatter_only, 'rules'),
        ('11-5 README deny block emptied, prose kept', m_readme_emptied, 'rules'),
        ('11-6 hook constant edited without regenerating', m_hook_constant, 'rules'),
        ('11-7 never-verb removed from rules.json without regenerating', m_rules_json, 'rules'),
        ('14 404 NOT_FOUND row removed (SLUG_NOT_FOUND stays)', m_trouble_row, 'rules'),
        ('16-1 generator puts the never-verbs in deny (blocks regenerated)', m_gen_verbs_deny, 'rules'),
        ('16-2 generator puts the raw-key commands in deny (blocks regenerated)', m_gen_raw_deny, 'rules'),
        ('16-3 generator makes Codex forbid the raw-key commands (old behaviour)', m_gen_codex_raw_forbid, 'rules'),
        ('16-3b Codex raw-key justification drops "never paste the key"', m_gen_codex_justification, 'rules'),
        ('16-4 SKILL.md tells Flo ! is fine for a key command', m_prose_bang, 'rules'),
        ('16-5 agent-rules.md drops "only when the user explicitly asks"', m_prose_unasked, 'rules'),
        ('16-6 tool-map.md row back to NEVER', m_toolmap_never, 'rules'),
    ]:
        d = copy_repo()
        fn(d)
        rc = run(gates[gate], d)
        print('%s %s (%s gate)' % ('RED ' if rc else 'SURVIVED', name, gate))
        if not rc:
            survived.append(name)
        shutil.rmtree(d)

    # --- scrub: one planted fixture per row; red with the row, green without it. `repo` rows are planted OUTSIDE
    # plugin/, so a scrub that goes back to scanning the payload only leaves them green and is caught here.
    rows = [ln for ln in open(os.path.join(ROOT, 'tools/scrub-patterns.txt'), encoding='utf-8').read().split('\n')
            if ln.strip() and not ln.startswith('#')]
    fixtures = [ln for ln in open(os.path.join(ROOT, 'tools/scrub-fixtures.txt'), encoding='utf-8').read().split('\n')
                if ln.strip() and not ln.startswith('#')]
    if len(rows) != len(fixtures):
        survived.append('scrub: %d rows but %d fixtures' % (len(rows), len(fixtures)))
    for i, (row, fx) in enumerate(zip(rows, fixtures)):
        d = tempfile.mkdtemp(prefix='flo-scrub-')
        os.makedirs(os.path.join(d, 'tools'))
        shutil.copy(os.path.join(ROOT, 'tools/scrub-check.sh'), os.path.join(d, 'tools'))
        where = 'plugin' if row.startswith('payload ') else 'evals'
        os.makedirs(os.path.join(d, where))
        open(os.path.join(d, where, 'f.md'), 'w').write(fx + '\n')
        open(os.path.join(d, 'tools/scrub-patterns.txt'), 'w').write('\n'.join(rows) + '\n')
        red = run(['bash', 'tools/scrub-check.sh'], d)
        rest = rows[:i] + rows[i + 1:]
        open(os.path.join(d, 'tools/scrub-patterns.txt'), 'w').write('\n'.join(rest or ['repo (?!)']) + '\n')
        green_without = run(['bash', 'tools/scrub-check.sh'], d) == 0
        ok = red and green_without
        print('%s scrub row %-48s fixture %r' % ('RED ' if ok else 'SURVIVED', row[:48], fx[:40]))
        if not ok:
            survived.append('scrub row ' + row)
        shutil.rmtree(d)

    survived += release_check_mutations()
    print('mutation-test: %d survived' % len(survived))
    return 1 if survived else 0


def release_check_mutations():
    """The release pin: each way of serving untagged or mismatched code must turn tools/release-check.py red."""
    survived = []
    claude, codex = '.claude-plugin/marketplace.json', '.agents/plugins/marketplace.json'

    def src(d, mf):
        p = os.path.join(d, mf)
        doc = json.load(open(p, encoding='utf-8'))
        return p, doc, [e for e in doc['plugins'] if e['name'] == 'workflow'][0]

    def setter(mf, fn):
        def m(d):
            p, doc, e = src(d, mf)
            fn(e)
            json.dump(doc, open(p, 'w', encoding='utf-8'), indent=2)
        return m

    def ref(v):
        def f(e):
            e['source']['ref'] = v
        return f

    def relative(e):
        e['source'] = './plugin'

    def other_repo(e):
        e['source']['url'] = 'https://github.com/someone/fork.git'

    def add_sha(e):
        e['source']['sha'] = '0' * 40

    def drop_ref(e):
        del e['source']['ref']

    cases = [
        ('pin a branch (main)', setter(claude, ref('main'))),
        ('Codex pins a branch (main)', setter(codex, ref('main'))),
        ('no ref: default branch', setter(claude, drop_ref)),
        ('Claude back to a relative ./plugin source', setter(claude, relative)),
        ('Codex back to a relative ./plugin source', setter(codex, relative)),
        ('the two marketplaces pin different tags', setter(codex, ref('v0.0.1'))),
        ('pin ahead of the plugin version', lambda d: [setter(m, ref('v99.0.0'))(d) for m in (claude, codex)]),
        ('source points at another repo', setter(claude, other_repo)),
        ('an extra selector rides along', setter(codex, add_sha)),
    ]
    for name, fn in cases:
        d = copy_repo()
        fn(d)
        rc = run([sys.executable, 'tools/release-check.py', '--no-git'], d)
        print('%s release pin: %s' % ('RED ' if rc else 'SURVIVED', name))
        if not rc:
            survived.append('release pin: ' + name)
        shutil.rmtree(d)

    # --release refuses a tag that is not the manifests' version, and one that is not ahead of the pin
    d = copy_repo()
    v = json.load(open(os.path.join(d, 'plugin/.claude-plugin/plugin.json'), encoding='utf-8'))['version']
    major, minor, _ = (int(x) for x in v.split('.'))
    for name, tag in (('release tag != plugin version', 'v%d.%d.0' % (major, minor + 1)),
                      ('release tag not vX.Y.Z', 'latest'),
                      ('release tag not ahead of the current pin', 'v0.0.0')):
        rc = run([sys.executable, 'tools/release-check.py', '--no-git', '--release', tag], d)
        print('%s release: %s' % ('RED ' if rc else 'SURVIVED', name))
        if not rc:
            survived.append('release: ' + name)
    shutil.rmtree(d)
    return survived


if __name__ == '__main__':
    sys.exit(main())
