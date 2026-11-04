# Troubleshooting Flo

## Engini refused a call (HTTP errors)

Flo stops and tells you when one of these comes back. What **you** do:

| Error | What it means | What you do |
|---|---|---|
| 403 `API_KEY_REQUIRED` | Your `engini_workflows` connection does not use a Developer API key. This is the most likely first-run failure | Re-create the connection in your own terminal: `engini connect engini_workflows`, choose **auth method 1 (`x-api-key`)** and paste a **workspace-scoped** Developer API key. Then start Flo again. Changing anything else does not help |
| 400 `SCOPE_REQUIRED` | Your key is not scoped to a workspace and environment. Writes always refuse it | Issue a workspace-scoped key in Engini, re-create the connection with it (as above), and log in again with `engini login` |
| 403 `PERMISSION_DENIED` | The key's user may not create or edit workflows in that workspace | Ask your Engini account admin for the permission, or use a key from a user who has it |
| 400 `INVALID_REQUEST` | Flo sent a malformed request | Flo fixes this himself; if it repeats, report it with the message |
| 404 `SLUG_NOT_FOUND` | A tool Flo asked for does not exist for your account | Usually an outdated plugin or CLI: update both. Flo re-searches the catalog |
| 404 `CONNECTION_NOT_FOUND` | A connection id Flo used is not usable here | Check `engini connections list`; the connection may have been deleted or belong to another workspace |
| 404 `NOT_FOUND` | A workflow or folder is not in this workspace, or you cannot read it | Check you are logged in to the right account and workspace (`engini whoami`) |
| 404 `UNKNOWN_FIELD` | Flo asked for options of a field that has none | Flo fixes this himself |
| 400 `OPTIONS_NOT_READONLY` | A field's options come from a source Flo will not read | Flo leaves the field empty and lists it; fill it in the designer |
| 422 `PLAN_HAS_ERRORS` | The plan still has errors; nothing was saved | Flo fixes them and asks you to approve again |
| 409 `WORKFLOW_ACTIVE` | You asked Flo to change a workflow that is turned on | Turn it off in the designer first, or let Flo create a new turned-off copy |
| 409 `REVISION_CONFLICT` | Someone saved the workflow after Flo read it | Flo re-reads it, re-applies the change and shows you the new proposal |
| 400 `SAVE_REJECTED` | The designer's own checks refused the save (connection ownership, schedule too frequent, AI tool names ...) | Read the message; Flo adjusts the plan and asks you again |
| 502 `VENDOR_ERROR` | The connected app failed while Flo read from it | The connection may need re-authorizing in Engini. Then retry |
| 500 `INTERNAL_ERROR` | An Engini server fault | Note the time and contact Engini support. Flo does not retry a write |

## Table automations

| Symptom | Cause | What you do |
|---|---|---|
| Flo asks for a table id | No Flo tool can list your tables yet | Open the table in Engini and copy the id from the address bar (`.../tables/<table id>`) |
| Flo asks for a column's field name | Flo must use the field name (such as `Text1`), not the column label, and cannot list columns yet | In the table, open **Manage Fields** and open the column's menu: **Field Name** is the value Flo needs |
| Compile says `TABLE_NOT_FOUND` | The id is not one of your tables in this workspace and environment | Check the id, and that you are logged in to the workspace the table lives in (`engini whoami`) |
| Compile says `TABLE_NOT_CHANGEABLE` | A table automation's table is set when it is created | Ask Flo for a new automation on the other table |
| A step reads an empty value at run time | The reference used a column label or an unknown name | Fix the reference in the designer with the column's field name; for "record updated", read `newValues.<field name>` |
| Flo cannot turn the automation on | Table automations are turned on only in the Engini app | Turn it on in the table's **Automations** tab |
| Flo cannot build a "button clicked" automation | That trigger is not available to Flo | Build it in the Engini designer |

## Setup problems

| Symptom | Cause | What you do |
|---|---|---|
| `engini: command not found` | The CLI is not installed or not on your path | `npm i -g @engini/cli`, then open a new terminal |
| Flo says the CLI is too old | Below 0.29.0, or `engini whoami --json` has no `workspace` key | `npm i -g @engini/cli@latest` |
| Flo says you are not logged in | No saved login | Run `engini login` yourself (interactive) |
| Flo says the key is not scoped | `engini whoami` shows no workspace | Log in with a workspace-scoped key |
| Flo finds no `engini_workflows` connection | You have not connected it yet | `engini connect engini_workflows`, auth method 1 (`x-api-key`), in your own terminal |
| A step shows "no connection" in the proposal | You have no connection for that app in this workspace | Connect the app in Engini, or connect the step in the designer after Flo creates the workflow |
| A dropdown that depends on another field is empty | Its options load only after the first field is set | Fill it in the designer; Flo lists every field it left empty |
| The account or workspace is not the one you expected | `ENGINI_API_KEY` is set in your environment and overrides your saved login | Unset it, or make it the key you meant |

## Install problems

| Symptom | Cause | What you do |
|---|---|---|
| The skill is not found right after installing | Both tools load plugins at session start | Start a new session |
| The Flo agent does not load in Codex | Codex may not install a plugin's agent definition (not yet verified) | Use the skill directly ("build an Engini workflow ...") |
| `/plugin details workflow@engini` shows `Hooks (0)` | The guard is not installed | Reinstall from `engini/skills`; check the plugin is enabled |
| The install check prints `FLO-CANARY-RAN` with no prompt | The guard did not run: no `python3`/`python` (3.8+) on your path, hooks disabled in your settings, the plugin disabled, or an older Claude Code - or your permission mode answered the prompt for you | Fix the cause; until then only your own settings (the safety block) stand in for it |
| The install check shows a prompt that does not contain `FLO-HOOK-ASK` | The prompt came from your own settings, not from the guard: the guard did not run | Same as above |

## "A command was blocked" or "Claude Code is asking me about a command" (Claude Code)

The message starts with **`FLO-HOOK-ASK`** (a prompt for you) or **`FLO-HOOK-DENY`** (a refusal the agent reads). It
comes from Flo's guard hook, installed with the plugin in `hooks/deny-never-verbs.py`. It applies to **every** Claude
Code session where the plugin is enabled - not only to Flo - so it can ask about or block your own commands too.
Removing it is a deliberate downgrade: only your own settings would be left. Which one you got:

| Message says | Why | What you do |
|---|---|---|
| **never-verb** (a prompt) | The command turns on/off, runs, reruns or deletes a workflow. Flo does this only when you explicitly asked for that action on that workflow | **Approve only if you asked for exactly this.** If you did not, answer No: Flo should not have tried. If the command only *names* one inside a plan's text, run the `engini tools call ... <<'EOF'` as its own command, opener on the first line: any other heredoc is checked as code |
| **unreadable tool name** (a prompt) | The tool name in `engini tools call` is built from a shell variable, a substitution or a pattern, so the guard cannot check it against the never list and it could be one of the four | Answer No unless you know what it runs. Better: have Flo write the tool name literally. If the tool name sits inside an inline `--args '{...}'` value, pass the arguments through `--args -` with a quoted heredoc instead |
| **raw-key command** (a refusal) | `engini connect`, `engini login`, `connections create/update/delete`, `auth-providers create/update` or `--api-key` | Run it yourself **in your own terminal, outside Claude Code or Codex** - not with the `!` prefix: in Claude Code's `!` mode the input is not a terminal, so the CLI cannot hide the key you type. Flo gives you the exact command; tell him when it is done |
| **key read** | It touches the CLI's stored login, an `ENGINI_*` key variable, or dumps the whole environment | Nothing to fix; check presence only, with `[ -n "$ENGINI_API_KEY" ]` |
| **protected file** | It edits the guard itself or your Claude Code / Codex settings | Make that change yourself |
| **unreadable hook input** | The guard could not read what Claude Code sent it, so it refused (it fails closed) | Update Claude Code; if it persists, report it |

To work without the guard for a session: `/plugin disable workflow@engini` (this removes all of its protections).

## "Nothing is ever blocked in Codex"

Expected: **Codex has no Flo hook.** The only thing that asks you before the four verbs and the key-handling
commands in Codex is the rules file from the README's safety block, saved as `~/.codex/rules/flo.rules`. If commands
are not asked about, check that file exists and that you started a new session after saving it. When Codex asks about a
key-handling command, decline it and run the command yourself in your own terminal, outside Codex: an approved one runs
through the agent.
