# Contributing to Flo

This repo is **public** and is the **source of truth** for Flo: the plugin, its gates, its evals and its release
workflow all live here, and there is no other copy to sync from. Everything you commit - code, comments, commit
messages - is published the moment it reaches GitHub, and stays fetchable from forks forever.

Customers never install `main`. Both marketplace manifests pin the plugin to a **release tag and its commit id**, so
work on `main` reaches nobody until a release moves the pin.

## Layout

| Path | What it is |
|---|---|
| `plugin/` | the plugin both tools install (only this directory is fetched, at the pinned tag) |
| `plugin/skills/build-engini-workflow/` | the shared core: `SKILL.md` + `references/**`, one copy for Claude Code and Codex |
| `plugin/agents/flo.md`, `plugin/.claude-plugin/plugin.json` | Claude Code adapter (frontmatter + a pointer, max 40 lines); the manifest declares `hooks` |
| `plugin/.codex/agents/flo.toml`, `plugin/.codex-plugin/plugin.json` | Codex adapter (a pointer, max 40 lines, no `model`) |
| `plugin/hooks/claude-hooks.json`, `plugin/hooks/deny-never-verbs.py` | the Claude Code guard hook. **Not** `hooks/hooks.json`: that name is both tools' default discovery path and would ship an unprobed Codex hook (Codex gets no hook) |
| `plugin/README.md`, `plugin/TROUBLESHOOTING.md` | customer docs |
| `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json` | marketplace manifests; each pins `skills` to `plugin/` of this repo at a release tag (`ref`) and commit (`sha`) |
| `README.md`, `LICENSE` | the repo landing page and licence |
| `tools/` | gates, generator, contract snapshot (development only, never installed) |
| `evals/` | model evals (development only, never installed) |
| `.github/` | CI, release and contract-check workflows; CODEOWNERS |

## Rules

- **Public from the first commit.** No staff or customer names, internal host names, internal ids (connections,
  apps, accounts, boards, tickets), internal repo paths, ticket/PR references, source file or class names of the
  Engini backend, or dates in prose - not in `plugin/`, not in `tools/`, not in a commit message. Examples use
  placeholders (`123`, `<slug>`, `example.com`). `tools/scrub-check.sh` checks the whole tree, and in CI the PR's
  commit messages and authors, for the generic shapes of these; `tools/scrub-literals.py` checks the tree and the
  commits against a private list of specific values (see "Scrub" below). The squash message you type when merging
  is checked only by the private list, so keep it plain.
- **The heavy content exists once.** Rules live in `SKILL.md` (what must hold even unread) and
  `references/agent-rules.md` (the full set). Adapters point at the skill; they never paraphrase a rule
  (`tools/adapter-check.sh` hashes each adapter against a fixed template).
- **What the hook refuses or asks about is defined once, in `tools/rules.json`.** The four `never_verbs` **ask** the
  user (the hook's `ask` decision, the settings `ask` list, Codex `prompt`); the `raw_key_*` commands are **refused**
  by the hook (the refusal tells the agent to hand the command to the user's own terminal, never to `!`), `ask` in the
  settings and `prompt` in Codex (no hook there; its justification tells the user to decline and run the command in
  their own terminal). Key reads, env dumps and self-protection stay deny. A refusal beats a question when one command
  trips both. `python3 tools/generate.py` writes the hook's constant block, the never-verb block in `SKILL.md` and
  the README settings block (its marker is still `flo:deny-block`). Never edit a generated block by hand; CI fails
  when one is stale.
- **The call shape** is in `tools/call-shape.txt`. Change it only together with the corpus and the hook (the hook
  strips exactly that heredoc shape).
- **Do not develop this repo with the published Flo plugin enabled.** Its guard refuses edits to `hooks/*hooks.json`,
  `deny-never-verbs` and any `.codex/` path - that is the guard working as intended.
- **Test your working tree, not the marketplace.** Adding this checkout as a marketplace installs the pinned tag, not
  your edits. Load the working tree directly: `claude --plugin-dir ./plugin`.

## Gates (CI runs all of them on every PR - `.github/workflows/ci.yml`)

```bash
python3 tools/generate.py --check      # generated blocks current
python3 tools/rules-check.py           # never-verbs in the SKILL body + README settings block (ask, not deny), tool-map drift, 15 HTTP codes in TROUBLESHOOTING
python3 tools/hook-selftest.py         # ~200 rows (allow / ask / deny), the hook's JSON output, open-on-purpose rows, 2 MB timing, the 21-slug contract snapshot
bash tools/scrub-check.sh              # leak check over the WHOLE repo (generic shapes, see below); --commits RANGE adds commits
python3 tools/scrub-literals.py        # the private term list from $SCRUB_DENYLIST (skips with a notice when unset)
bash tools/adapter-check.sh            # adapters hash to their templates; one skill dir; no symlinks
python3 tools/release-check.py         # both marketplaces pin the same existing release tag + commit; no v* branch on origin
python3 tools/mutation-test.py         # every gate above goes red under its known mutations
claude plugin validate --strict plugin
claude plugin validate --strict .
claude plugin validate --strict --profile directory plugin
```

CI checks out with `fetch-depth: 0`: `release-check.py` needs the tags, and the scrub needs the PR's commits.

**Scrub.** `tools/scrub-patterns.txt` holds one Python regex per row with a scope: `repo` rows apply to every file,
`payload` rows only to `plugin/` (stricter shapes the tooling itself cannot meet, such as `.claude/` paths in the hook
self-test). The rows are generic shapes - internal host names, 9-12 digit ids, ticket refs, `#` plus digits, id assignments
of four or more digits, home-directory paths, backend class-name families, UUIDs, dates in prose, non-example email
addresses, key-shaped values - **never a list of real values**: a list of what must not leak would leak it. Each
row has a made-up fixture in `tools/scrub-fixtures.txt`; `mutation-test.py` plants it (`repo` rows outside
`plugin/`) and requires red with the row and green without it; shapes one fixture line cannot hold (email-exemption
bypasses, commit identities) are extra cases in `mutation-test.py`. When a legitimate line trips a row, change the line
(use a placeholder) before you consider narrowing the row.

**Private term list.** Generic shapes cannot catch a specific name or id, and a public list of them would leak them.
So the specific values live in the repository secret `SCRUB_DENYLIST` (one term per line; plain text, not a
credential), kept by the maintainers outside this repo. `tools/scrub-literals.py` reads it from the environment and
scans every file (no file skipped except the rule lines of the two scrub shape files; their comment lines are
scanned) plus the given commits, and on a hit prints only `file:line` or `commit line`, never the term - CI logs are
public. To see what matched, run it locally with the list: `SCRUB_DENYLIST="$(cat <list>)" python3 tools/scrub-literals.py`.
CI runs it on every PR and push (a PR from a fork gets no secrets: the step prints a notice and skips, and the push run
on `main` catches it); the release runs it over the tree and every commit since the last release tag with
`--require`, so a release cannot run without the list. `mutation-test.py` proves it goes red with a made-up list.

**Release pin.** `tools/release-check.py` fails when either marketplace serves untagged code: a relative
`./plugin` source, a branch `ref`, no `ref`, no full `sha`, another repo, the two manifests pinning different tags or
commits, a pin ahead of the plugin version, a pinned tag that does not exist, a `sha` that is not the tag's commit or
an ancestor of it with the same `plugin/` tree, or any `v*` branch on `origin`. Both tools install `sha` when it is set;
`ref` alone is a name, and a branch with the tag's name would be installed instead of the tag. `mutation-test.py`
proves each of these red, the git-backed ones in a throwaway repo with a local `origin`.

Model evals (`evals/`) need a logged-in Claude Code and cost tokens, so they are not in CI:

```bash
python3 evals/run-claude.py --pass 2 --no-hook-control   # the wire: ask token + zero stub argv; removing the hook turns the ask/deny cases red
python3 evals/run-claude.py --pass 1                     # model behaviour with the hook OFF
python3 evals/run-claude.py --settings readme            # the README's pasted settings alone, hook removed
python3 evals/run-claude.py --pass 2 --case wire-allow-rule --no-hook-control   # hook ask vs the README's allow rule (not yet run)
evals/run-codex.sh                                       # not yet run - needs codex
```

The evals run **as you**. `run-claude.py` puts a stub `engini` first on `PATH`, kills `ENGINI_API_KEY`, forces
`--permission-mode default` and denies reads of the stored-login file. Do not loosen any of that: pass 1 runs with
the hook off on purpose, and a model asked to "print my key" otherwise reads your real one.

## Releasing

1. In a normal PR: bump `version` in **both** plugin manifests (`plugin/.claude-plugin/plugin.json`,
   `plugin/.codex-plugin/plugin.json`) to `X.Y.Z`, with the release notes in the PR description. Merge it. Customers
   still get the previous tag.
2. Run the **release** workflow (Actions -> release -> Run workflow, from `main`, input `tag` = `vX.Y.Z`). Its
   `gates` job (no environment, no credential):
   - checks the tag: `vX.Y.Z`, equal to both plugin manifests' version, not yet existing, ahead of the current pin,
     and no `v*` branch on `origin`;
   - runs the private term list over the tree and every commit since the last release tag (fails without the list);
   - runs every gate above on the `main` commit, including the npm-installed Claude Code validators, and validates
     the bumped manifests.

   Then its `release` job, after the `skills-release` environment's reviewer approves, checks out exactly the gated
   commit and runs only `python3` and `git` (no npm in the job that holds the App token). It:
   - makes **one** commit on top of that commit, `Release vX.Y.Z` by the release identity, that changes only the two
     marketplace pins to `ref` `vX.Y.Z` and `sha` = the gated commit, and tags **that** commit `vX.Y.Z` (annotated).
     `plugin/` in the tagged commit is byte-identical to the gated commit (so the gated commit is a valid `sha`: the
     release commit cannot hold its own id), and a marketplace added at the tag (`...skills.git#vX.Y.Z`) pins itself;
   - pushes `main` and the tag with one `git push --atomic` using the release App's token: both land or neither does.
     If `main` moved during the run the push is rejected (never forced) and nothing is released; run it again.
3. Publish a GitHub Release for the tag with the notes.

**Release notes** must flag any change to the never list or the hook, and give the SHA-256 of
`plugin/hooks/deny-never-verbs.py` (the release log prints it). Neither tool auto-updates Flo, so a guard fix reaches
nobody until they update; the minimum versions in `plugin/README.md` double as the deprecation lever.

Codex can be checked by hand before a release: `codex plugin marketplace add <this dir>` and an install that lists the
skill (not yet run - no Codex on the build machine).

## Supply chain

- **Write access here is code execution on every installer's workstation, next to their Engini key** - `hooks/`
  ships and runs on every tool call. Re-check who has write access at each release.
- `.github/CODEOWNERS` covers `SKILL.md`, `plugin/hooks/`, `tools/`, `.github/` and all four manifests. Two-person
  review needs a rule requiring approval including a code owner, and a second named owner - **not set yet**; until
  then `main` is protected by the rules below.
- **Branch protection on `main`:** pull requests required, the `gates` check (CI) required, no force-push, no
  deletion; the release App is the only actor allowed to push directly (the release commit). **Tag ruleset on
  `v*`:** only the release App may create, nobody may update or delete - a moved tag would silently change what every
  pinned install fetches. **Branch ruleset on `v*`:** nobody may create, update or delete a branch named `v*`, with no
  bypass - a branch named like a release tag would be installed in its place (`release-check.py` checks this too).
- **The release credential lives in the environment, not the repo.** Required reviewers gate only jobs that declare
  the environment; a repository secret is readable by any workflow on any branch. So (admin settings, once):
  - `FLO_RELEASE_APP_KEY` is an **environment secret** of `skills-release`, never a repository secret.
    `FLO_RELEASE_APP_ID`, `FLO_RELEASE_NAME`, `FLO_RELEASE_EMAIL` are not secrets (the App id and the bot identity)
    and may be repository or environment variables;
  - the environment has a **required reviewer**, its **deployment branches** are restricted to `main`, and admins
    **cannot bypass** it;
  - `SCRUB_DENYLIST` (the private term list) is a repository secret: plain text, not a credential, read by CI and
    the release's `gates` job. Pull requests from forks never receive it;
  - `ENGINI_CONTRACT_KEY` (the daily contract check) is a repository secret: a **read-only**, workspace-scoped key
    with no write permissions. Pull requests from forks never receive it.
- Neither tool signs or verifies a plugin. The pinned install line (`...skills.git#vX.Y.Z`) is the documented one for
  anyone who reviews what they install.
- **Codex has no Flo hook** (Codex directory distribution; `rules/*.rules` from the README is its only layer). Do not
  add `hooks/hooks.json` or an `extensions."com.openai".hooks` key; reversing that needs the Codex hook behaviour
  probed first.

## Server contract

What can actually break installed customers is the **server contract**: `tools/contract-check.py` (daily in
`contract-check.yml`) diffs `engini tools list/get` for the `engini_workflows` tools against
`tools/contract/snapshot.json`, read-only, and fails when a never-verb disappears or is renamed - the one drift that
turns the guard's ask into a silent no-op. Everything else it reports as info. Update the snapshot with
`python3 tools/contract-check.py --update` in a reviewed PR.
