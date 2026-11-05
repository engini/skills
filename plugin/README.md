# Flo - build Engini workflows from a plain-language request

Flo is an agent for **Claude Code** and **Codex**. You describe a workflow ("when a deal closes in Salesforce, post to
Slack"); Flo designs it, dry-runs it against your own Engini account, shows you a proposal, and creates it **only
after you approve** - always **turned off**. You finish and turn it on in the Engini designer.

Flo works through the `engini` command-line tool, on your own login and your own API-key connection. It does
nothing your key could not do by hand - which is also the honest limit of every safety measure below.

## Before you start

| You need | Version | Why |
|---|---|---|
| An Engini account and a **workspace-scoped Developer API key** | - | Flo can only write with a key scoped to one workspace and environment. Ask for a dedicated, least-privilege key: a key carries its creator's whole permission set |
| The Engini CLI: `npm i -g @engini/cli` | **0.29.0 or later** | every Flo call goes through it |
| Claude Code | **2.1.316 or later** (the version this release was tested on) | |
| Python | **3.8 or later**, as `python3` or `python` | Claude Code only: runs Flo's guard hook (below) |
| Codex | not yet verified on a real Codex install | see "Codex" below |

`jq` is not needed.

## Install

**Claude Code** - in your terminal:

```text
claude plugin marketplace add engini/skills
claude plugin install skills@engini
```

(or `/plugin marketplace add engini/skills` and `/plugin install skills@engini` inside a session).

The marketplace pins Flo to a **release tag**: you install the last tagged release, never unreleased work on `main`.
To stay on one reviewed release even when you update, add the marketplace pinned to its tag instead:
`claude plugin marketplace add https://github.com/engini/skills.git#vX.Y.Z` (the release notes give the tag).
Claude Code does not update plugins on its own; neither tool signs or verifies a plugin, so the pinned form is the
one to use if you review what you install.

**Codex** (not yet verified on a real Codex install - treat these lines as provisional)

```text
codex plugin marketplace add engini/skills --sparse .agents/plugins
```

The Codex marketplace pins Flo to the same release tag. To stay on one release, add it pinned:
`codex plugin marketplace add engini/skills --ref vX.Y.Z --sparse .agents/plugins`.

Then install **skills** from the `/plugins` browser and start a **new session** - the skill is not found until you do.
Codex has no Flo hook (see "What Flo will never do on his own"), so also paste the Codex rules from the safety block below.

## Check the install - this must fail loudly if something is wrong

**Claude Code.** Run `/plugin details skills@engini`. It must list **Skills (1)**, **Agents (1)** and **Hooks (1)**.
`Hooks (0)` means the guard is not installed and nothing but your own settings asks you before the four never-verbs.

Then prove the guard actually runs. Ask Claude to run this exact command (it is harmless either way: it makes a
throwaway fake `engini` in a temp folder and puts it first on the path, so your real CLI and account are never
touched):

```bash
d=$(mktemp -d) && printf '#!/bin/sh\necho FLO-CANARY-RAN\n' > "$d/engini" && chmod +x "$d/engini" && PATH="$d:$PATH" engini tools call engini_workflows_delete_workflow --args -
```

- Claude Code **asks you to confirm** the command, and the prompt text starts with **`FLO-HOOK-ASK`** - the guard
  is working. Answer **No**; answering Yes is harmless too (the fake CLI just prints `FLO-CANARY-RAN`).
- It prints **`FLO-CANARY-RAN`** with no prompt - the guard did **not** run (no Python on the path, hooks disabled in
  your settings, the plugin disabled, or an older Claude Code), or your permission mode answered the prompt for you.
  Fix that before you rely on it.
- A prompt or a permission-denied message that does **not** contain `FLO-HOOK-ASK` - that came from your own
  settings (the safety block below), not from the guard, which did **not** run. Fix that too.

Never test the guard with a real never-verb against your real `engini`: if the guard is missing and you approve the
prompt, that is a real delete on your account.

## Connect Engini (in your own terminal)

1. `engini login` - interactive. Never `engini login --api-key ...`: arguments end up in your shell history and in
   the process list.
2. `engini connect engini_workflows` - choose **auth method 1 (`x-api-key`)** and paste your workspace-scoped key.
   Any other auth method fails every builder call with `403 API_KEY_REQUIRED`.

Run both yourself **in your own terminal, outside Claude Code or Codex** - not with Claude Code's `!` prefix. The CLI
hides the key you type only when its input is a terminal, and in Claude Code's `!` mode it is not (`process.stdin.isTTY`
is false there), so a key typed that way would show. Flo's guard refuses to let the agent run these commands, because
they put a raw key in the agent's hands; when Flo needs one done he stops and gives you the command to run in your own
terminal, never asks you to paste a key into the chat, and never puts a key in a command. `!` is fine for a check with
no secret in it, such as `! engini whoami`. Whether Codex's shell gives the CLI a terminal is not verified - use your
own terminal there too.

## First run

Ask for a workflow in plain words - "Build a workflow in my Engini account: every weekday at 8:00, fetch
https://example.com/report and email it to me". Flo:

1. checks the CLI version, your login (account / workspace / environment) and your `engini_workflows` connection;
2. compiles a throwaway plan to confirm which workspace and environment your connection writes to;
3. searches the catalog, reads each step's schema and dropdown options, and compiles the plan until it is clean;
4. stops and shows you a **proposal table** - every step, the target workspace and environment the compile echoed,
   the connection id and a fingerprint;
5. creates the workflow **only** when you approve that proposal in the conversation, quoting its fingerprint. The
   workflow is created **turned off**.

You finish in the Engini designer: connect any step Flo could not connect (Flo lists them), fill fields it left
empty on purpose, and turn the workflow on.

**Flo will:** design, dry-run, propose, create or update workflows you approved - always turned off.
**Flo won't** (on his own): turn a workflow on or off, run it, rerun an execution or delete a workflow. He does one of
these only when you explicitly ask for that action on that workflow, and you get a permission prompt each time.
**Flo never:** creates or changes a connection, or handles your API key - when a step needs one he stops and gives you
the command to run in your own terminal.

## What Flo will never do on his own, and what actually stops him

The four never-verbs - the only four tools Flo asks you about by name. He never calls one on his own initiative; he
calls one only when you explicitly ask for that action on that workflow, and Claude Code then **asks you to approve
each call**:

<!-- flo:never-list:begin -->
<!-- generated from the rules source - do not edit by hand -->
- `engini_workflows_delete_workflow`
- `engini_workflows_run_workflow`
- `engini_workflows_enable_or_disable_workflow`
- `engini_workflows_rerun_execution`
<!-- flo:never-list:end -->

Four layers stand between them and your account. Only the last one is a boundary, and it refuses nothing:

1. **Flo's instructions** say: never on his own initiative; only when you explicitly ask for that exact action, after
   telling you a permission prompt is coming. Prose: a model follows it, nothing enforces it.
2. **Flo's guard hook - Claude Code only.** Installed with the plugin and live at once. It **asks you to confirm** an
   `engini tools call` naming any of the four verbs listed above, in any argument order and through quoting, case
   and `bash -c` wrappers; a tool name it cannot read (built from a shell variable or a substitution, such as
   `engini_workflows_$V`) is asked about too, because it could be one of the four. A question is a prompt, not a
   block: it works only while your permission mode lets the prompt reach you. It **refuses** `engini connect`,
   `engini login`, `engini connections create|update|delete` and `engini connections auth-providers create|update`
   and any `--api-key` when the agent runs them, and tells the agent to hand you the command to run in your own
   terminal; it refuses reading the CLI's stored login (below) or an `ENGINI_API_KEY` / `ENGINI_API_TOKEN` /
   `ENGINI_COMPANY_TOKEN` variable, or dumping the environment (a presence test `[ -n "$ENGINI_API_KEY" ]` is
   fine); and edits to the hook itself or to your Claude Code or Codex settings - including any command that
   names your `.claude` or `.codex` folder itself, a wildcard name or a `.`/`..` step inside one, or a `cd` into a
   folder under one (so even `ls ~/.claude` is refused). Read, Write, Edit, Grep and Glob paths are judged as
   given and again after resolving them against the session's folder and following symlinks. An
   `engini tools call` with a heredoc is judged as code unless it is Flo's own one-call shape: the `<<'EOF'` opener
   ends the command's first line and the reader is the `engini` CLI itself (`engini`, `npx @engini/cli` or
   `npx @engini/cli@<exact version>`).

   **This applies to every project's own `.claude` and `.codex` folders too.** With the plugin enabled,
   `ls .claude`, `git add .claude`, `grep -r x .claude` and a `cd` into a folder inside `.claude` are refused in
   every project and every session, not only while Flo is working. Run those in your own terminal or turn the plugin off for the
   session.
3. **Your own settings** - the safety block below. Copy-paste; a plugin cannot install it for you.
4. **The Engini server** refuses nothing here: your key is allowed to do all of it.

**Codex has no hook.** In Codex the rules file you paste from the safety block is the **only** layer besides Flo's
instructions; if you skip it, nothing asks you before the four verbs or the key-handling commands. Those commands
only ask in Codex, they are not refused: if you approve one, it runs through the agent and the key would pass through
it. So **decline** the prompt and run the command yourself in your own terminal, outside Codex. Flo's instructions
say he never runs them himself and never asks you to paste a key into the chat.

**Permission modes.** What the Claude Code docs say, not something we ran end to end:

- default mode: the guard's question for a never-verb reaches you. That a hook's question also beats the
  `Bash(engini:*)` allow rule below has not been verified yet; your `ask` rules cover the same four verbs either way.
- auto mode: documented to still send a hook's question to you (the classifier does not decide it), and to still
  prompt on `ask` rules in your settings.
- `--dangerously-skip-permissions` (bypass): what a hook's question does here is **undocumented**, and one unverified
  report says it is approved for you, so assume the guard's question may not reach you. The docs say `ask` rules in
  your settings still prompt in this mode, so **paste the safety block below** - those rules are the layer that holds
  in bypass mode. They match the literal command form only (see below).
- `-p` (non-interactive): nobody can answer, so the docs say the call is refused rather than asked. `dontAsk` is
  expected to do the same (inferred, not documented for a hook).

Do not run Flo with `--dangerously-skip-permissions`: he holds a shell and your key.

**While Flo has a shell and your key, he can do anything your key can do, including acting through your other
connections.** The guard narrows one literal command form. It is a text matcher, not a sandbox. Deliberately open,
and tested as open:

- **every other tool**: the guard asks about only the four verbs. Flo's rule against calling other apps' tools (for
  example `slack_send_message`) is an instruction he follows, not something enforced; so is "read execution data
  only when asked". Builder tools Engini adds later run normally too;
- indirection the guard never sees: `eval "$X"`, `bash -c "$X"`, a shell function, a script file;
- anything that skips the CLI: a `python -c` against the SDK, or a plain HTTPS call with your key;
- a tool name that is never in the command text at all, e.g. `xargs engini tools call --args - < slugfile`;
- the key file reached through a glob (`cd ~/.config && cat engini/conf*`), a recursive search from a parent
  folder in the shell (`grep -r ... ~/.config`), and a custom `XDG_CONFIG_HOME` folder named by its own path in a
  shell command;
- a settings folder name built from a variable or a wildcard in the folder name itself (`~/.cl*`);
- in the shell, a symlink to your settings or key folder that already exists (the command names only the link),
  and a program that changes folder itself before it writes (`os.chdir` in a script, `git -C`, `find -execdir`).
  Read, Write, Edit, Grep and Glob follow symlinks, so those tools are covered.

**Scope.** The guard applies to **every** Claude Code session where the plugin is enabled - not only while Flo is
working. It asks you before *your own* never-verb call (approve it - you meant it) and refuses *your own*
`engini connections delete` or `engini login` when the agent runs it: run those in your own terminal, or turn the plugin
off for the session with `/plugin disable skills@engini` (that removes the guard's other protections too). Everything
else - your builds, git, other tools, other Engini apps' tools - runs normally.

When the guard speaks, the message starts with `FLO-HOOK-ASK` (a prompt for you, for a **never-verb** you should approve
only if you asked for it, or a **tool name it cannot read**) or `FLO-HOOK-DENY` (a refusal the agent reads, for a
**raw-key command**, a **key read** or a **protected file**). A command that trips both is refused. See
TROUBLESHOOTING.md.

Claude Code's own permission rules (layer 3) match the four verbs inside a compound command such as
`cd /tmp && engini tools call ...` - tested for deny rules on Claude Code 2.1.316; the permissions docs say deny and
ask rules apply when any subcommand of a compound command matches them, so the ask rules below are expected to match the
same way, but that was not re-tested. The guard's extra reach is that it needs no paste, and the quoting and
wrapper forms above.

## Safety block - paste it yourself

Each rule matches the **literal command form only**. `bash -c`, a shell variable, `eval`, reordered arguments or a
`python -c` against the SDK walk past every one of them. They are what holds when the guard does not run, and in
Codex they are all there is.

- **Allow only `Bash(engini:*)`** and never run Flo with `--dangerously-skip-permissions`. Flo holds a shell and your
  key; this is the widest control by far.
- The `ask` rules make Claude Code ask **you**, outside the conversation, before every create or update, before each
  of the four never-verbs and before the key-handling commands (`engini login`, `engini connect`, `engini connections
  create|update|delete`, `engini connections auth-providers create|update`, `engini login --api-key`) - the approvals
  the model cannot give itself. With Flo's guard installed those last commands are refused outright when the agent
  runs them, so the `ask` rule is what applies when the guard is not installed; in Codex, which has no guard, the rules
  file only asks, so an approved command there would carry the key through the agent: decline it and run the command
  yourself in your own terminal. Only
  the stored-login `Read` rules, the one `cat` rule and the environment dumps are `deny`.
- The `Read` rules cover the stored login on each platform for Claude's own file tools; they do not bind a shell
  command, and the one `Bash(cat ...)` rule covers only that exact command. What keeps other shell reads (`grep`,
  `head`, the other paths) from running unasked is that `Bash(engini:*)` is the only `allow` rule, so any other
  command asks you first.

<!-- flo:deny-block:begin -->
<!-- generated from the rules source - do not edit by hand -->
**Claude Code** - merge into your user settings (`settings.json` in your `~/.claude` folder):

```json
{
  "permissions": {
    "allow": [
      "Bash(engini:*)"
    ],
    "ask": [
      "Bash(engini tools call engini_workflows_create_workflow_from_plan:*)",
      "Bash(engini tools call engini_workflows_update_workflow_from_plan:*)",
      "Bash(engini tools call engini_workflows_delete_workflow:*)",
      "Bash(engini tools call engini_workflows_run_workflow:*)",
      "Bash(engini tools call engini_workflows_enable_or_disable_workflow:*)",
      "Bash(engini tools call engini_workflows_rerun_execution:*)",
      "Bash(engini connect:*)",
      "Bash(engini login:*)",
      "Bash(engini connections create:*)",
      "Bash(engini connections update:*)",
      "Bash(engini connections delete:*)",
      "Bash(engini connections auth-providers create:*)",
      "Bash(engini connections auth-providers update:*)",
      "Bash(engini login --api-key:*)"
    ],
    "deny": [
      "Read(~/.config/engini/**)",
      "Read(~/AppData/Roaming/engini/**)",
      "Read(~/engini/config.toml)",
      "Bash(cat ~/.config/engini/config.toml)",
      "Bash(printenv:*)",
      "Bash(env)"
    ]
  }
}
```

**Codex** - save as `~/.codex/rules/flo.rules`:

```python
# Flo: a prompt before every write, before the four never-verbs and before the raw-key commands (decline those and run them yourself).
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_create_workflow_from_plan"], decision = "prompt")
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_update_workflow_from_plan"], decision = "prompt")
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_delete_workflow"], decision = "prompt", justification = "Flo calls this only when you asked for exactly this action on this workflow")
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_run_workflow"], decision = "prompt", justification = "Flo calls this only when you asked for exactly this action on this workflow")
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_enable_or_disable_workflow"], decision = "prompt", justification = "Flo calls this only when you asked for exactly this action on this workflow")
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_rerun_execution"], decision = "prompt", justification = "Flo calls this only when you asked for exactly this action on this workflow")
prefix_rule(pattern = ["engini", "connect"], decision = "prompt", justification = "takes or stores a raw API key - decline this, run it in your own terminal outside Codex, never paste the key into the chat")
prefix_rule(pattern = ["engini", "login"], decision = "prompt", justification = "takes or stores a raw API key - decline this, run it in your own terminal outside Codex, never paste the key into the chat")
prefix_rule(pattern = ["engini", "connections", "create"], decision = "prompt", justification = "takes or stores a raw API key - decline this, run it in your own terminal outside Codex, never paste the key into the chat")
prefix_rule(pattern = ["engini", "connections", "update"], decision = "prompt", justification = "takes or stores a raw API key - decline this, run it in your own terminal outside Codex, never paste the key into the chat")
prefix_rule(pattern = ["engini", "connections", "delete"], decision = "prompt", justification = "takes or stores a raw API key - decline this, run it in your own terminal outside Codex, never paste the key into the chat")
prefix_rule(pattern = ["engini", "connections", "auth-providers", "create"], decision = "prompt", justification = "takes or stores a raw API key - decline this, run it in your own terminal outside Codex, never paste the key into the chat")
prefix_rule(pattern = ["engini", "connections", "auth-providers", "update"], decision = "prompt", justification = "takes or stores a raw API key - decline this, run it in your own terminal outside Codex, never paste the key into the chat")
```
<!-- flo:deny-block:end -->

Where the CLI stores your login (the guard refuses reads that name any of these paths, and Grep/Glob searches
started from a folder above them such as your home folder or `~/.config` - however that folder is spelled: a relative
path, no path while the session runs in it, a symlink, or a second macOS name for your home folder such as the one
under `/System/Volumes/Data`):

- `~/.config/engini/config.toml` (macOS, Linux)
- `$XDG_CONFIG_HOME/engini/config.toml` (when `XDG_CONFIG_HOME` is set)
- `%APPDATA%\engini\config.toml` (Windows)
- `%USERPROFILE%\engini\config.toml` (Windows, when `APPDATA` is unset)

**Codex sandbox.** Codex runs commands without network by default, so every `engini` call fails. Allow network for
commands (`[sandbox_workspace_write]` `network_access = true` in your Codex config) or approve the commands outside
the sandbox. Flo's optional session log and lessons live in `~/.engini/flo/`, outside the workspace: add it as a
writable root or Flo skips them. Not yet verified on a real Codex install.

## Things to know

- **Your key carries its creator's whole permission set.** Use a dedicated, least-privilege, workspace-scoped key
  you can rotate.
- **Log in interactively, in your own terminal.** `engini login`, never `--api-key` on the command line and never
  through Claude Code's `!` prefix (no terminal there, so the key cannot be hidden as you type it).
- **What Flo reads enters the model's context**: workflow definitions, and execution data when you ask for it.
- **The stored key is reachable by the agent.** It is a file in your own home folder; the agent can reach it through
  the shell as much as through file reads. The guard refuses the literal reads; what actually protects you is a
  scoped, rotatable key plus the `Bash(engini:*)` allow rule - not secrecy from the model.

## Moving from workflow@engini

Version 0.6.0 renamed the plugin from `workflow` to `skills`. The marketplace is still `engini` and the agent is still
**Flo**; only the plugin's name changed, so the agent is now `skills:flo` and the skill is now
`/skills:build-engini-workflow` (it still loads on its own when your request matches). An existing `workflow@engini`
install keeps working on its last release but gets no further updates. To move:

**Claude Code**

```text
/plugin uninstall workflow@engini
/plugin marketplace update engini
/plugin install skills@engini
```

Then start a **new session** and run the install check above for `skills@engini`. If your `settings.json` (user or
project) still names `workflow@engini` - an `enabledPlugins` entry, or an `extraKnownMarketplaces` entry added for it -
remove that entry: it points at a plugin the marketplace no longer serves.

**Codex:** remove the **workflow** plugin in `/plugins`, install **skills** from the same browser, and start a new
session.

The safety block above does not change: it names the `engini` CLI's commands, not the plugin.

## Moving from flo@engini-flo

Version 0.3.0 renamed the install: the marketplace became `engini` and the plugin `workflow`; version 0.6.0 renamed the
plugin again, to `skills` (the agent is still **Flo**; its skill is now `/skills:build-engini-workflow`). The repo is
now `engini/skills`; the old `engini/flo-plugin` and `engini/workflow-plugin` addresses redirect to it, so an existing
`flo@engini-flo` install keeps working until you move. To move:

**Claude Code**

```text
/plugin uninstall flo@engini-flo
/plugin marketplace remove engini-flo
/plugin marketplace add engini/skills
/plugin install skills@engini
```

**Codex:** remove the old **flo** plugin and the `engini-flo` marketplace in `/plugins`, then add
`engini/skills --sparse .agents/plugins` as shown under Install and install **skills**
from the browser. Start a new session afterwards.

## Updating and uninstalling

- **Update:** `/plugin marketplace update engini`, then reinstall (`/plugin install skills@engini`); in Codex,
  upgrade from `/plugins`. Neither tool updates Flo on its own, so a fix to the never list or the guard reaches you
  only when you update. Release notes flag every such change and give the guard script's SHA-256.
- **Uninstall:** `/plugin uninstall skills@engini` (Claude Code) or remove it in `/plugins` (Codex). Remove the
  safety block from your settings if you no longer want it.

Trouble? See TROUBLESHOOTING.md.
