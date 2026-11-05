# Engini skills

Engini's agent plugins for **Claude Code** and **Codex**. Today it holds one plugin, **skills**: **Flo**, an agent
that builds Engini workflows from a plain-language request ("when a deal closes in Salesforce, post to Slack"). Flo
designs the workflow, dry-runs it against your own Engini account, shows you a proposal, and creates it **only after
you approve** - always **turned off**.

**Read [plugin/README.md](plugin/README.md) before you install**: what you need (an Engini workspace-scoped API key,
the `engini` CLI), how to check the install, the safety settings to paste, and what Flo will never do on its own.

## Install

**Claude Code**

```text
claude plugin marketplace add engini/skills
claude plugin install skills@engini
```

**Codex** (not yet verified on a real Codex install - provisional)

```text
codex plugin marketplace add engini/skills --sparse .agents/plugins
```

Then install **skills** from the `/plugins` browser and start a new session.

## Releases

You always install a **tagged release**, never unreleased work on `main`: both marketplace manifests pin the plugin to
a release tag and its commit id, and only a release moves the pin. To stay on one release even when you update, add the marketplace at
its tag: `claude plugin marketplace add https://github.com/engini/skills.git#vX.Y.Z`, or
`codex plugin marketplace add engini/skills --ref vX.Y.Z --sparse .agents/plugins`. See
[Releases](https://github.com/engini/skills/releases) for the notes and the guard script's SHA-256.

This repo was `engini/workflow-plugin`; the old address redirects here.

## Moving from workflow@engini

Version 0.6.0 renamed the plugin from `workflow` to `skills`. The marketplace is still `engini`, the agent is still
**Flo** (now `skills:flo`) and the skill is now `/skills:build-engini-workflow`. To move in Claude Code:

```text
/plugin uninstall workflow@engini
/plugin marketplace update engini
/plugin install skills@engini
```

Then start a new session. In Codex: remove **workflow** in `/plugins`, install **skills** from the same browser and
start a new session. If your `settings.json` still names `workflow@engini` in `enabledPlugins` (or carries an
`extraKnownMarketplaces` entry added for it), remove that entry. Details: [plugin/README.md](plugin/README.md).

## Contributing

This repo is the source of truth for Flo - the plugin, its gates, evals and release workflow. See
[CONTRIBUTING.md](CONTRIBUTING.md). Trouble with an install: [plugin/TROUBLESHOOTING.md](plugin/TROUBLESHOOTING.md).

Licensed under the [MIT License](LICENSE).
