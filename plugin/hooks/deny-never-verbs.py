#!/usr/bin/env python3
"""Flo guard - a Claude Code PreToolUse hook (Python 3.8+).

Refuses: the four never-verb `engini tools call` slugs (and any tool name it cannot read), the engini commands
that take or store a raw API key, reads of the engini CLI's stored login or key variables, and edits to this hook
or the user's agent settings. Every other command and every other tool slug passes.

A text matcher, not a sandbox: indirection (eval, a shell function, a script file) and anything that skips the
CLI never reach it. It writes nothing, logs nothing and never echoes the text it judged (it may hold a key).
Fail-closed inside: unreadable input or an internal error denies.
"""
import json
import os
import posixpath
import re
import sys

# BEGIN GENERATED from tools/rules.json by tools/generate.py - do not edit by hand
DENY_TOKEN = 'FLO-HOOK-DENY'
NEVER_VERBS = frozenset(['engini_workflows_delete_workflow', 'engini_workflows_enable_or_disable_workflow', 'engini_workflows_rerun_execution', 'engini_workflows_run_workflow'])
CALL_VALUE_FLAGS = frozenset(['--args', '--connection', '--file', '--llm', '--max-bytes', '--tool-call-id', '--toolset'])
RAW_KEY_COMMANDS = (('connect',), ('connections', 'auth-providers', 'create'), ('connections', 'auth-providers', 'update'), ('connections', 'create'), ('connections', 'delete'), ('connections', 'update'), ('login',))
RAW_KEY_FLAGS = ('--api-key',)
KEY_ENV = '(?:ENGINI_API_KEY|ENGINI_API_TOKEN|ENGINI_COMPANY_TOKEN)'
KEY_PATH = ('(?:\\.config|XDG_CONFIG_HOME\\}?|APPDATA%?|AppData[\\\\/]+Roaming)[\\\\/]+engini\\b', '[\\\\/]engini[\\\\/]+config\\.toml')
SELF_PROTECT = ('deny-never-verbs', 'hooks[\\\\/][A-Za-z0-9_-]*hooks\\.json', '(?<![A-Za-z0-9_-])\\.claude[\\\\/]+(?:plugins|settings)', '(?<![A-Za-z0-9_-])\\.codex[\\\\/]', '(?<![A-Za-z0-9_-])\\.(?:claude|codex)[\\\\/]*(?=[\\s;&|)\'"]|\\Z)', '(?<![A-Za-z0-9_-])\\.claude[\\\\/]+[^\\s\\\\/]*[*?\\[{$`]', '(?<![A-Za-z0-9_-])\\.(?:claude|codex)[\\\\/](?:[^\\s\\\\/;&|<>]*[\\\\/])*\\.\\.?(?=[\\\\/\\s;&|)\'"<>`]|\\Z)', '(?<![A-Za-z0-9_-])(?:cd|pushd|chdir|Set-Location|Push-Location|sl)[ \\t(]+[^;&|\\n]*\\.(?:claude|codex)[\\\\/]')
# END GENERATED

R_NEVER = DENY_TOKEN + ": never-verb. This engini tool turns on/off, runs, reruns or deletes a workflow - it is on Flo's never list (plugin README, 'What Flo will never do'). If you mean it, do it yourself in the Engini app."
R_UNREADABLE = DENY_TOKEN + ": unreadable tool name. The tool name in this engini command is built from a variable, a substitution or a pattern, so it cannot be checked against Flo's never list. Write the slug literally."
R_RAW_KEY = DENY_TOKEN + ": raw-key command. This engini command takes or stores an API key (connect, login, connections create/update/delete, auth-providers create/update, --api-key). Run it yourself in your own terminal."
R_KEY_READ = DENY_TOKEN + ": key read. This reads the engini CLI's stored login, an Engini key variable or the whole environment. Only a presence test such as [ -n \"$ENGINI_API_KEY\" ] is allowed."
R_SELF = DENY_TOKEN + ": protected file. This changes Flo's guard hook or your agent settings. Change those yourself."
R_BAD_INPUT = DENY_TOKEN + ": unreadable hook input, refused (the guard fails closed)."

FILE_TOOLS = ('Read', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit')
WRITE_TOOLS = ('Edit', 'Write', 'MultiEdit', 'NotebookEdit')
SEARCH_TOOLS = ('Grep', 'Glob')
SHELL_TOOLS = ('Bash', 'PowerShell')
MAX_DEPTH = 24
SLUG_SHAPE = re.compile(r'[A-Za-z0-9_-]+\Z')
REDIRECT = re.compile(r'\d*(?:<<<|<<|>>|>\||[<>])')
FLO_HEREDOC = re.compile(r"<<'([A-Za-z_]+)'[ \t]*\Z")
PLAIN_PREFIX = re.compile(r'[A-Za-z0-9_@./:=, \t-]*\Z')
PRESENCE = re.compile(r'(?:\[\[?|\btest)[ \t]+-[nz][ \t]+("?)\$(?:' + KEY_ENV + r'|\{' + KEY_ENV + r'\})\1(?:[ \t]+\]\]?)?'
                      r'|(?i:\bTest-Path[ \t]+Env:' + KEY_ENV + r'\b)')
ENV_DUMP = re.compile(r'/proc/[^/\s]+/environ|(?i:(?<![$\w])env:|GetEnvironmentVariables)')
KEY_PATH_RE = re.compile('|'.join(KEY_PATH), re.I)
SELF_RE = re.compile('|'.join(SELF_PROTECT), re.I)
KEY_ENV_RE = re.compile(KEY_ENV)
# A folder that holds the key folder (home, ~/.config, %APPDATA%, a drive or filesystem root): a recursive Grep or
# Glob from it reaches the key without naming it. Matched on the normalised path (/ separators, no trailing /).
KEY_ANCESTOR = re.compile(r"""\A(?:
    (?: ~[^/]* | \$HOME | \$\{HOME\} | %USERPROFILE% | \$env:USERPROFILE | /root | /var/root
      | (?:[A-Za-z]: | /[A-Za-z])? (?:/(?:Users|home)(?:/[^/]+)?)? )
    (?:/\.config | /AppData(?:/Roaming)?)?
  | \$XDG_CONFIG_HOME | \$\{XDG_CONFIG_HOME\} | %APPDATA% | \$env:APPDATA | \.config | AppData(?:/Roaming)?
)\Z""", re.I | re.X)
RUN = {False: re.compile(r"[^\s;&|'\"\\`(){}]+"), True: re.compile(r"[^\s;&|'\"`(){}]+")}
UNESCAPE = {False: re.compile(r'\\(.)'), True: re.compile(r'`(.)')}
NEEDS_SCAN = re.compile(r"[\s;&|'\"`(){}$\\]")
BRACKETS = {'(': re.compile(r'[()]'), '{': re.compile(r'[{}]')}
ASSIGNMENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*=')
NPX_CLI = re.compile(r'@engini/cli(?:@\d+\.\d+\.\d+[\w.+-]*)?\Z', re.I)


def _close(text, i):
    """Index of the bracket closing text[i] (nesting-aware), or len(text) when unbalanced."""
    depth = 0
    for m in BRACKETS[text[i]].finditer(text, i):
        depth += 1 if m.group() == text[i] else -1
        if depth == 0:
            return m.start()
    return len(text)


def segments(text, ps=False, depth=0, out=None):
    """Split shell text into segments (lists of words), shell-style: quotes join a word, escapes are dropped.
    Every quoted span, $( ), backtick, ( ) and { } is ALSO scanned as segments of its own, so nothing hides
    inside one - an opener adds a segment, it never ends the one it sits in."""
    if out is None:
        out = []
    if depth > MAX_DEPTH:
        raise ValueError('nesting')
    esc = '`' if ps else '\\'
    run = RUN[ps]
    seg, word, i, n = [], [], 0, len(text)

    def end_word():
        if word:
            seg.append(''.join(word))
            del word[:]

    def inner(s):
        if NEEDS_SCAN.search(s):
            segments(s, ps, depth + 1, out)

    while i < n:
        c = text[i]
        if c in ' \t\r':
            end_word()
            i += 1
        elif c in '\n;&|':
            end_word()
            if seg:
                out.append(seg)
                seg = []
            i += 1
        elif c == esc:
            if i + 1 < n and text[i + 1] != '\n':
                word.append(text[i + 1])
            i += 2
        elif c == "'":
            j = text.find("'", i + 1)
            j = n if j < 0 else j
            word.append(text[i + 1:j])
            inner(text[i + 1:j])
            i = j + 1
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == esc else 1
            body = text[i + 1:min(j, n)]
            word.append(UNESCAPE[ps].sub(r'\1', body))
            inner(body)
            i = j + 1
        elif c == '`':
            j = text.find('`', i + 1)
            j = n if j < 0 else j
            word.append(text[i:j + 1])
            inner(text[i + 1:j])
            i = j + 1
        elif c in '({':
            j = _close(text, i)
            word.append(text[i:j + 1])
            inner(text[i + 1:j])
            i = j + 1
        elif c in ')}':
            word.append(c)
            i += 1
        else:
            m = run.match(text, i)
            word.append(m.group())
            i = m.end()
    end_word()
    if seg:
        out.append(seg)
    return out


def _is_cli(tok):
    t = tok.lower()
    return (t == 'engini' or t.endswith(('/engini', '\\engini', 'engini.cmd', 'engini.exe', 'cli.js'))
            or t == '@engini/cli' or t.startswith('@engini/cli@'))


def candidates(seg, k):
    """Every token after `call` (at seg[k]) that the CLI could take as the tool slug: not a flag, not a
    value-taking flag's value, not a redirection."""
    out, skip = [], False
    for tok in seg[k + 1:]:
        if skip:
            skip = False
        elif tok.startswith('-'):
            skip = tok in CALL_VALUE_FLAGS
        elif REDIRECT.match(tok):
            skip = REDIRECT.fullmatch(tok) is not None
        else:
            out.append(tok)
    return out


def judge_call(seg):
    """Family 1: deny-list on `tools call` (any segment, every occurrence)."""
    if 'tools' not in ' '.join(seg).lower():
        return None
    for i in range(len(seg) - 1):
        if seg[i].lower() != 'tools':
            continue
        nxt = seg[i + 1]
        if nxt.lower() == 'call':
            for tok in candidates(seg, i + 1):
                if tok.lower() in NEVER_VERBS:
                    return R_NEVER
                if not SLUG_SHAPE.match(tok):
                    return R_UNREADABLE
        elif re.search(r'[$`(]', nxt) and any(_is_cli(t) for t in seg):
            return R_UNREADABLE
    return None


def judge_named(seg):
    """Family 1b: a never-verb named anywhere else (curl, python -c, a flag value...). A token with whitespace in
    it is a quoted multi-word string; its words are judged as a segment of their own."""
    if 'engini_workflows_' not in ' '.join(seg).lower():
        return None
    has_call = any(seg[i].lower() == 'tools' and seg[i + 1].lower() == 'call' for i in range(len(seg) - 1))
    for j, tok in enumerate(seg):
        low = tok.lower()
        if low in NEVER_VERBS or ('engini_workflows_' in low and re.search(r'[^A-Za-z0-9_]', tok)
                                  and not re.search(r'\s', tok)):
            exempt = not has_call and j >= 2 and seg[j - 2].lower() == 'tools' and seg[j - 1].lower() == 'get'
            if not exempt:
                return R_NEVER if low in NEVER_VERBS else R_UNREADABLE
    return None


def judge_raw_key(seg):
    """Family 2: engini commands that take or store a raw key."""
    blob = ' '.join(seg).lower()
    if 'engini' not in blob and 'cli.js' not in blob:
        return None
    for k, tok in enumerate(seg):
        if not _is_cli(tok):
            continue
        rest = seg[k + 1:]
        if any(t.lower().startswith(RAW_KEY_FLAGS) for t in rest):
            return R_RAW_KEY
        words = [t.lower() for t in rest if not t.startswith('-')]
        if any(tuple(words[:len(cmd)]) == cmd for cmd in RAW_KEY_COMMANDS):
            return R_RAW_KEY
    return None


def judge_env_dump(seg):
    """Family 4, token half: bare environment dumps."""
    words = list(seg)
    while words and (ASSIGNMENT.match(words[0]) or words[0] in ('sudo', 'command', 'exec', 'nohup', 'time')):
        words.pop(0)
    if not words:
        return None
    cmd, args = words[0].rsplit('/', 1)[-1], words[1:]
    if cmd == 'printenv':
        return R_KEY_READ
    if cmd == 'env' and not [a for a in args if not a.startswith('-') and '=' not in a]:
        return R_KEY_READ
    if cmd in ('set', 'export', 'declare', 'typeset') and all(a.startswith('-') for a in args):
        if cmd != 'set' or not args:
            return R_KEY_READ
    return None


def strip_flo_heredoc(text):
    """Drop the body of the ONE shipped heredoc a command may start with, and only that: the opener ends the
    command's FIRST line, that line is plain words, and the heredoc's reader is the engini CLI itself (or
    `shasum -a 256` / `sha256sum` for the proposal fingerprint). The body is plan JSON, not commands. Anything
    else - an opener on a later line, a quote, `#`, `$` or `;` before it, `sh -s`/`bash -s` reading it - is left in
    and scanned like code (fail closed). Works on RAW lines: in a quoted heredoc bash ends the body at the first line
    equal to the delimiter and does not join a trailing backslash, so continuations are joined only afterwards."""
    lines = text.split('\n')
    m = FLO_HEREDOC.search(lines[0])
    if not m or not _shipped_start(lines[0][:m.start()]):
        return text
    try:
        end = lines.index(m.group(1), 1)
    except ValueError:
        return text
    return '\n'.join([lines[0][:m.start()]] + lines[end + 1:])


def _cli_invocation(words):
    """Exactly one engini CLI invocation and nothing else: `engini`, `npx @engini/cli[@v]`, `node .../cli.js`."""
    if len(words) == 1:
        return _is_cli(words[0]) and not words[0].lower().endswith('cli.js')
    if len(words) == 2:
        # npx: the package itself, bare or at an exact version - not an alias (@npm:x) or a git spec (@github:a/b),
        # which npx resolves to some other program
        return ((words[0] == 'npx' and NPX_CLI.match(words[1]) is not None)
                or (words[0] == 'node' and words[1].lower().endswith('cli.js')))
    return False


def _shipped_start(prefix):
    # plain words only: no quote, `#`, `$`, backslash, backtick, bracket, separator or redirect before the opener
    if not PLAIN_PREFIX.match(prefix):
        return False
    seg = prefix.split()
    if seg in (['shasum', '-a', '256'], ['sha256sum']):
        return True
    for k in range(len(seg) - 1):
        if seg[k] == 'tools' and seg[k + 1] == 'call':
            cands = candidates(seg, k + 1)
            args_stdin = any(seg[x] == '--args' and seg[x + 1] == '-' for x in range(k, len(seg) - 1)) or '--args=-' in seg
            return (_cli_invocation(seg[:k]) and args_stdin and bool(cands) and judge_call(seg) is None
                    and all(SLUG_SHAPE.match(c) and c.lower() not in NEVER_VERBS for c in cands))
    return False


def judge_shell(cmd, ps):
    text = cmd if ps else strip_flo_heredoc(cmd)
    text = text.replace('`\n' if ps else '\\\n', '')
    plain = re.sub(r"['\"`\\]" if ps else r"['\"\\]", '', text)
    for t in (text, plain, _dots(plain)):
        if SELF_RE.search(t):
            return R_SELF
        if KEY_PATH_RE.search(t):
            return R_KEY_READ
    rest = PRESENCE.sub(' ', text)
    if KEY_ENV_RE.search(rest) or KEY_ENV_RE.search(re.sub(r"['\"`\\]", '', rest)) or ENV_DUMP.search(rest):
        return R_KEY_READ
    for seg in segments(text, ps):
        for judge in (judge_call, judge_named, judge_raw_key, judge_env_dump):
            reason = judge(seg)
            if reason:
                return reason
    return None


def _str(ti, key, required):
    v = ti.get(key)
    if v is None and not required:
        return ''
    if not isinstance(v, str):
        raise ValueError(key)
    return v


def _norm(path):
    p = posixpath.normpath(path.replace('\\', '/'))
    return '' if p == '/' else p.rstrip('/')


def _dots(text):
    """Shell text with `/./` and `/name/../` collapsed, so ~/.config/./engini reads as ~/.config/engini."""
    prev = None if re.search(r'[\\/]\.', text) else text
    while prev != text:
        prev = text
        text = re.sub(r'[\\/]\.(?=[\\/])', '', text)
        text = re.sub(r'[\\/](?!\.\.?[\\/\s])[^\s\\/;&|<>]+[\\/]\.\.(?=[\\/\s;&|)<>]|\Z)', '', text)
    return text


def _reals(path, cwd):
    """The path as the tool may open it: ~ expanded, joined to the session's cwd, symlinks resolved - once with `..`
    taken physically (the OS) and once lexically (a caller that normalises first: /tmp/.. is / there, /private here)."""
    joined = os.path.join(cwd, os.path.expanduser(path))
    return sorted({os.path.realpath(joined), os.path.realpath(os.path.normpath(joined))})


def _within(real, folder):
    """`real` relative to folder (after resolving folder), or None when it is outside."""
    top = os.path.realpath(os.path.expanduser(folder))
    if real == top:
        return ''
    return real[len(top):].lstrip(os.sep) if real.startswith(top.rstrip(os.sep) + os.sep) else None


def _agent_dirs():
    env = os.environ
    return [('.claude', d) for d in ('~/.claude', env.get('CLAUDE_CONFIG_DIR')) if d] + \
           [('.codex', d) for d in ('~/.codex', env.get('CODEX_HOME')) if d]


def _key_dirs():
    """The engini CLI's configPath() folders (engini-sdk ts/packages/cli/src/config.ts)."""
    env = os.environ
    return [os.path.join(b, 'engini') for b in (env.get('XDG_CONFIG_HOME'), os.path.expanduser('~/.config'),
                                                  env.get('APPDATA'), env.get('USERPROFILE')) if b]


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _file_forms(path, cwd):
    """Every spelling of a file tool's target the patterns are tried on: as given, normalised, resolved, and - when
    it resolves into a real agent-settings folder - re-spelled under that folder's own name (.claude or .codex), so
    the name patterns see it."""
    reals = _reals(path, cwd)
    forms = [path, _norm(path)] + reals
    for real in reals:
        for name, d in _agent_dirs():
            rest = _within(real, d)
            if rest is not None:
                forms.append('/' + name + ('/' + rest.replace(os.sep, '/') if rest else ''))
    return forms, reals


def _reaches_key(real):
    """True when `real` is a key folder, inside one, or a folder above one (compared by inode, so a symlink, a
    macOS firmlink (the home folder again under /System/Volumes/Data) or a relative path cannot dodge it)."""
    for kd in _key_dirs():
        if _within(real, kd) is not None:
            return True
        a = os.path.realpath(kd)
        while True:
            if real == a or _same(real, a):
                return True
            up = os.path.dirname(a)
            if up == a:
                break
            a = up
    return False


def decide(raw_stdin):
    """The deny reason for one PreToolUse payload, or None to allow. Never raises."""
    try:
        payload = json.loads(raw_stdin)
        if not isinstance(payload, dict) or not isinstance(payload.get('tool_input'), dict):
            return R_BAD_INPUT
        tool, ti = payload.get('tool_name'), payload['tool_input']
        cwd = payload.get('cwd') if isinstance(payload.get('cwd'), str) and payload.get('cwd') else os.getcwd()
        if tool in SHELL_TOOLS:
            return judge_shell(_str(ti, 'command', True), tool == 'PowerShell')
        if tool in FILE_TOOLS:
            path = _str(ti, 'notebook_path' if tool == 'NotebookEdit' and 'file_path' not in ti else 'file_path', True)
            forms, reals = _file_forms(path, cwd)
            if tool in WRITE_TOOLS and any(SELF_RE.search(f) for f in forms):
                return R_SELF
            if any(KEY_PATH_RE.search(f) for f in forms) or any(_reaches_key(r) for r in reals):
                return R_KEY_READ
            return None
        if tool in SEARCH_TOOLS:
            path = _str(ti, 'path', False)
            names = [_str(ti, k, False) for k in ('glob', 'pattern') if k == 'glob' or tool == 'Glob']
            # path and glob compose (path ~/.config + glob engini/*), so judge them joined, not side by side
            probes = [path] + names + [path + '/' + x for x in names if path and x]
            if any(KEY_PATH_RE.search(t) for t in probes) or (path and KEY_ANCESTOR.match(_norm(path))):
                return R_KEY_READ
            # an empty path searches the cwd; resolved, a relative or alternate-home spelling is caught too
            if any(_reaches_key(r) for r in _reals(path or '.', cwd)):
                return R_KEY_READ
            return None
        return R_BAD_INPUT
    except Exception:
        return R_BAD_INPUT


def main():
    try:
        raw = sys.stdin.buffer.read().decode('utf-8')
    except Exception:
        raw = ''
    reason = decide(raw)
    if reason:
        sys.stdout.write(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
