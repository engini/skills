# Connections

Two different kinds of connection are in play. Never mix them up.

## 1. Flo's door into the account: the user's `engini_workflows` connection

- The user's own connection of application `engini_workflows`, **auth method 1 (API key, header `x-api-key`)**,
  holding a key the user issued in their own account. The user creates it; Flo never creates, updates or deletes a
  connection and never handles the key.
- Find it: `engini connections list --application engini_workflows --json`. None -> **STOP** and ask the user to
  create one. Several -> ask which one; never pick silently.
- The key must be **workspace-scoped**: create/update refuse an unscoped key with `400 SCOPE_REQUIRED`. Reads and
  `compile_workflow_plan` do **not** refuse one - they fall back to the account's default workspace + Production,
  which can mislead. Two stops, both before any design work: `engini whoami --json` with an empty `workspace` (the
  login key), and a preflight compile whose `workspaceId` / `environmentId` differ from `whoami`'s `workspace.id` /
  `environment.id` (the connection holds a different key) -> STOP and tell the user the connection needs a
  workspace-scoped key.
- The key pins account, workspace and environment server-side; nothing in a plan or header can move a write elsewhere.
- `engini whoami` reports the **login** key's scope; a write lands in the **connection** key's scope. Only
  `compile_workflow_plan` echoes the latter (`workspaceId` / `environmentId`), so compile and write through the same
  connection id.
- A connection that is not an API key is refused on every builder tool with `403 API_KEY_REQUIRED`.

## 2. The steps' connections inside the account

Each `action` step / trigger has `connection`:

| Value | Result |
|---|---|
| `"auto"` (default) | The designer's own pick rule: the activity's own connector, then the app's non-default connections, then the app's default connection. Credential activities and another account's default connection get none. On an edit, a step keeps its saved connection while it is still usable |
| `"none"` / `"0"` | No connection - `MISSING_CONNECTION` warning |
| `"<id>"` | One of `list_builder_connections` for that app in this workspace/env, else `FOREIGN_CONNECTION` |

- List them: `engini_workflows_list_builder_connections` `{"app":"<app slug>"}` -> `[{connectionId, name, isDefault}]`.
- With several candidates, propose the choice to the user; do not let `auto` silently pick one they didn't mean.
- Flo never creates connections. A step without one is created anyway with a `MISSING_CONNECTION` warning; the user
  connects it in the designer.
- **Activation guard:** turning on an AI-built workflow is refused with `MISSING_CONNECTION` while any step whose app
  requires a connection has none. Flo never turns it on anyway; the user does after connecting.
- Dropdown labels and per-connection objects are read through the step's connection. No connection ->
  `NEEDS_CUSTOMER_INPUT` (value kept, label empty). Changing a step's connection re-reads its labels and objects.
