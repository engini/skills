# Connections

Two different kinds of connection are in play. Never mix them up.

## 1. Flo's door into the account: the user's own CLI login

- Every `engini workflows` command runs as the key the `engini` CLI is logged in with - the user's own
  workspace-scoped Developer API key, stored by `engini login` in their own terminal. Flo never logs in, never
  switches accounts (no `ENGINI_API_KEY`, no other config folder, no `--api-key`) and never handles the key.
- `engini whoami --json` shows the login's account, workspace and environment. The key must be
  **workspace-scoped**: create/update refuse an unscoped key with `400 SCOPE_REQUIRED`, and reads and compile fall
  back to the account's default workspace + Production, which can mislead. Two stops, both before any design work:
  `whoami` with an empty `workspace`, and a preflight compile whose `workspaceId` / `environmentId` differ from
  `whoami`'s `workspace.id` / `environment.id`.
- The key pins account, workspace and environment server-side; nothing in a plan or header can move a write elsewhere.
- **The lookup connection.** The CLI has no folder or workflow list, so resolving a folder or a workflow by name uses
  the `engini_workflows` tools through `engini tools call` and the user's own `engini_workflows` connection
  (auth method 1, API key, header `x-api-key`) - the same for a never-verb the user explicitly asks for. Find it with
  `engini connections list --application engini_workflows --json`; several -> ask which. It must hold a key for the
  login's workspace and environment: a `get_folders` row with another `workspaceId` / `environmentId` -> STOP. A
  connection that is not an API key is refused with `403 API_KEY_REQUIRED`. The user creates it; Flo never creates,
  updates or deletes a connection.

## 2. The steps' connections inside the account

Each `action` step / trigger has `connection`:

| Value | Result |
|---|---|
| `"auto"` (default) | The designer's own pick rule: the activity's own connector, then the app's non-default connections, then the app's default connection. Credential activities and another account's default connection get none. On an edit, a step keeps its saved connection while it is still usable |
| `"none"` / `"0"` | No connection - `MISSING_CONNECTION` warning |
| `"<id>"` | One of `engini workflows connections --app <slug>` for that app in this workspace/env, else `FOREIGN_CONNECTION` |

- List them: `engini workflows connections --app <app slug>` -> `[{connectionId, name, isDefault, applicationId}]`.
- With several candidates, propose the choice to the user; do not let `auto` silently pick one they didn't mean.
- Flo never creates connections. A step without one is created anyway with a `MISSING_CONNECTION` warning; the user
  connects it in the designer.
- **Activation guard:** turning on an AI-built workflow is refused with `MISSING_CONNECTION` while any step whose app
  requires a connection has none. Flo never turns it on anyway; the user does after connecting.
- Dropdown labels and per-connection objects are read through the step's connection. No connection ->
  `NEEDS_CUSTOMER_INPUT` (value kept, label empty). Changing a step's connection re-reads its labels and objects.
