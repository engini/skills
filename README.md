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

**Claude Code**

```text
/plugin marketplace add engini/flo-plugin
/plugin install flo@engini-flo
```

To stay on one reviewed release, add the marketplace pinned to its tag instead:
`/plugin marketplace add https://github.com/engini/flo-plugin.git#vX.Y.Z` (the release notes give the tag).
Claude Code does not update plugins on its own; neither tool signs or verifies a plugin, so the pinned form is the
one to use if you review what you install.

**Codex** (not yet verified on a real Codex install - treat these two lines as provisional)

```text
codex plugin marketplace add https://github.com/engini/flo-plugin.git --sparse .agents/plugins
```

Then install **flo** from the `/plugins` browser and start a **new session** - the skill is not found until you do.
Codex has no Flo hook (see "What Flo will never do"), so also paste the Codex rules from the safety block below.

## Check the install - this must fail loudly if something is wrong

**Claude Code.** Run `/plugin details flo@engini-flo`. It must list **Skills (1)**, **Agents (1)** and **Hooks (1)**.
`Hooks (0)` means the guard is not installed and nothing but your own settings stops the four never-verbs.

Then prove the guard actually runs. Ask Claude to run this exact command (it is harmless either way: it makes a
throwaway fake `engini` in a temp folder and puts it first on the path, so your real CLI and account are never
touched):

```bash
d=$(mktemp -d) && printf '#!/bin/sh\necho FLO-CANARY-RAN\n' > "$d/engini" && chmod +x "$d/engini" && PATH="$d:$PATH" engini tools call engini_workflows_delete_workflow --args -
```

- The result says **`FLO-HOOK-DENY`** - the guard is working.
- It prints **`FLO-CANARY-RAN`** - the guard did **not** run (no Python on the path, hooks disabled in your
  settings, the plugin disabled, or an older Claude Code). Fix that before you rely on it.
- It prints a **permission-denied** message and neither of the two above - your own settings (the safety block
  below) caught it, but the guard still did **not** run. Fix that too.

Never test the guard with a real never-verb against your real `engini`: if the guard is missing, that is a real
delete on your account.

## Connect Engini (in your own terminal)

1. `engini login` - interactive. Never `engini login --api-key ...`: arguments end up in your shell history and in
   the process list.
2. `engini connect engini_workflows` - choose **auth method 1 (`x-api-key`)** and paste your workspace-scoped key.
   Any other auth method fails every builder call with `403 API_KEY_REQUIRED`.

Run both yourself, outside Claude Code or Codex. Flo's guard refuses to let the agent run them, because they put a
raw key in the agent's hands.

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
**Flo won't:** turn a workflow on or off, run it, rerun an execution, delete a workflow, create or change a
connection, or handle your API key.

## What Flo will never do, and what actually stops him

The four never-verbs - the only four tools Flo refuses by name:

<!-- flo:never-list:begin -->
<!-- generated from the rules source - do not edit by hand -->
- `engini_workflows_delete_workflow`
- `engini_workflows_run_workflow`
- `engini_workflows_enable_or_disable_workflow`
- `engini_workflows_rerun_execution`
<!-- flo:never-list:end -->

Four layers stand between them and your account. Only the last one is a boundary, and it refuses nothing:

1. **Flo's instructions** name them as never. Prose: a model follows it, nothing enforces it.
2. **Flo's guard hook - Claude Code only.** Installed with the plugin and live at once. It refuses an
   `engini tools call` naming any of the four verbs listed above, in any argument order and through quoting, case
   and `bash -c` wrappers; a tool name it cannot read (built from a shell variable or a substitution, such as
   `engini_workflows_$V`) is refused too, because it could be one of the four. It also refuses `engini connect`,
   `engini login`, `engini connections create|update|delete` and `engini connections auth-providers create|update`
   and any `--api-key`; reading the CLI's stored login (below) or an `ENGINI_API_KEY` / `ENGINI_API_TOKEN` /
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
instructions; if you skip it, nothing enforces the four verbs at all.

**While Flo has a shell and your key, he can do anything your key can do, including acting through your other
connections.** The guard narrows one literal command form. It is a text matcher, not a sandbox. Deliberately open,
and tested as open:

- **every other tool**: the guard refuses only the four verbs. Flo's rule against calling other apps' tools (for
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
working. It also refuses *your own* `engini connections delete` or a never-verb you genuinely meant to run. Run
those in your own terminal, or turn the plugin off for the session with `/plugin disable flo@engini-flo` (that
removes the guard's other protections too). Everything else - your builds, git, other tools, other Engini apps' tools -
runs normally.

When the guard refuses something, the message starts with `FLO-HOOK-DENY` and says which of these it is: a
**never-verb** (intended - do not work around it), a **tool name it cannot read** (write the slug literally), a
**raw-key command**, a **key read** or a **protected file**. See TROUBLESHOOTING.md.

Claude Code's own deny rules (layer 3) also catch the four verbs inside a compound command such as
`cd /tmp && engini tools call ...` - tested on Claude Code 2.1.316. The guard's extra reach is that it needs no
paste, and the quoting and wrapper forms above.

## Safety block - paste it yourself

Each rule matches the **literal command form only**. `bash -c`, a shell variable, `eval`, reordered arguments or a
`python -c` against the SDK walk past every one of them. They are what holds when the guard does not run, and in
Codex they are all there is.

- **Allow only `Bash(engini:*)`** and never run Flo on auto-accept or `--dangerously-skip-permissions`. Flo holds a
  shell and your key; this is the widest control by far.
- The two `ask` rules make Claude Code ask **you**, outside the conversation, before every create or update - the one
  approval the model cannot give itself.
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
      "Bash(engini tools call engini_workflows_update_workflow_from_plan:*)"
    ],
    "deny": [
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
      "Bash(engini login --api-key:*)",
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
# Flo: the four never-verbs, the raw-key commands, and a prompt before every write.
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_delete_workflow"], decision = "forbidden", justification = "Flo never turns on, runs, reruns or deletes a workflow")
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_run_workflow"], decision = "forbidden", justification = "Flo never turns on, runs, reruns or deletes a workflow")
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_enable_or_disable_workflow"], decision = "forbidden", justification = "Flo never turns on, runs, reruns or deletes a workflow")
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_rerun_execution"], decision = "forbidden", justification = "Flo never turns on, runs, reruns or deletes a workflow")
prefix_rule(pattern = ["engini", "connect"], decision = "forbidden", justification = "takes or stores a raw API key - run it yourself")
prefix_rule(pattern = ["engini", "login"], decision = "forbidden", justification = "takes or stores a raw API key - run it yourself")
prefix_rule(pattern = ["engini", "connections", "create"], decision = "forbidden", justification = "takes or stores a raw API key - run it yourself")
prefix_rule(pattern = ["engini", "connections", "update"], decision = "forbidden", justification = "takes or stores a raw API key - run it yourself")
prefix_rule(pattern = ["engini", "connections", "delete"], decision = "forbidden", justification = "takes or stores a raw API key - run it yourself")
prefix_rule(pattern = ["engini", "connections", "auth-providers", "create"], decision = "forbidden", justification = "takes or stores a raw API key - run it yourself")
prefix_rule(pattern = ["engini", "connections", "auth-providers", "update"], decision = "forbidden", justification = "takes or stores a raw API key - run it yourself")
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_create_workflow_from_plan"], decision = "prompt")
prefix_rule(pattern = ["engini", "tools", "call", "engini_workflows_update_workflow_from_plan"], decision = "prompt")
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
- **Log in interactively.** `engini login`, never `--api-key` on the command line.
- **What Flo reads enters the model's context**: workflow definitions, and execution data when you ask for it.
- **The stored key is reachable by the agent.** It is a file in your own home folder; the agent can reach it through
  the shell as much as through file reads. The guard refuses the literal reads; what actually protects you is a
  scoped, rotatable key plus the `Bash(engini:*)` allow rule - not secrecy from the model.

## Updating and uninstalling

- **Update:** `/plugin marketplace update engini-flo`, then reinstall (`/plugin install flo@engini-flo`); in Codex,
  upgrade from `/plugins`. Neither tool updates Flo on its own, so a fix to the never list or the guard reaches you
  only when you update. Release notes flag every such change and give the guard script's SHA-256.
- **Uninstall:** `/plugin uninstall flo@engini-flo` (Claude Code) or remove it in `/plugins` (Codex). Remove the
  safety block from your settings if you no longer want it.

Trouble? See TROUBLESHOOTING.md.
