# `engini_workflows` tool map (builder)

The `engini_workflows` application carries 21 tools (`engini tools list --application engini_workflows`). The
argument names below were read from the live schema (`engini tools get`). Re-check before the first call of a run -
the live schema wins over this file (read `input_schema.required` and `input_schema.properties`):

```bash
engini tools get engini_workflows_<verb> --json
```

The live schema lists every argument under `required`, including ones the server treats as optional: the
**Required** column below is what you must send.

Every call (the arguments go through stdin; nothing is written to disk):

```bash
engini tools call engini_workflows_<verb> --args - --connection <connection id> --max-bytes 0 <<'EOF'
{"q":"send email","kind":"action"}
EOF
```

`--connection` is the user's own `engini_workflows` connection (auth method 1, API key `x-api-key`) - the one the
preflight compile resolved, and the same id for the compile and the write. `--max-bytes 0` keeps schemas and plans
from being truncated and keeps results out of the CLI's local result cache. Ids are JSON numbers.

## 1. Builder tools

API-key connections only (`403 API_KEY_REQUIRED` otherwise).

| Slug | Purpose | Required | Optional | Args example |
|---|---|---|---|---|
| `engini_workflows_search_builder_catalog` | Find triggers, actions, blocks the designer picker shows this account. Returns `[{slug, kind, app, name, description, score}]` | `q` | `kind` (`action` / `trigger` / `block`), `app`, `top` (default 10, max 100) | `{"q":"send email","kind":"action","app":"gmail","top":10}` - the text argument is `q`; `query` is ignored and returns the same unfiltered list for every search |
| `engini_workflows_get_builder_tool_schema` | Input/output schema + `dynamicFields` (the dropdown fields) + `subItems` (row tables like Http Queries/Headers: `tables`/`fields`/`manyRows` - never inputs). With `connectionId` it reads the connected system (per-connection objects and enums) | `slug` | `connectionId`, `kind` - add both for an action/trigger (live per-connection read), leave them out for a `block.*` | `{"slug":"<slug>","kind":"action","connectionId":123}` - the argument is `slug`, not `tool` |
| `engini_workflows_get_builder_field_options` | Option `{id,label}` list of ONE dropdown field, read through one of the user's connections. Also serves a filter field with `hasOptions` (field = the filter field). Slug `model.{provider}` + field `model` reads an AI agent's model list through the model connection (404 `UNKNOWN_FIELD` for `model.azure_openai`; 502 when the list cannot be read) | `slug`, `field`, `connectionId` | `kind` | `{"slug":"<slug>","field":"BOARD_ID","connectionId":123,"kind":"action"}` |
| `engini_workflows_list_builder_connections` | The user's connections of one app in the key's workspace/environment: `[{connectionId, name, isDefault, applicationId}]`. `app` also takes `model.{provider}`: the connections an AI agent's model of that provider can run on | `app` | - | `{"app":"<exact catalog app slug or app-{id}>"}` - without `app`: 400 "Name the app". The catalog can hold duplicate/draft/test apps: prefer the plain slug |
| `engini_workflows_compile_workflow_plan` | Dry run: compile + validate, saves nothing (may read the vendor for dropdown labels). Returns `{name, steps, jumps, diagnostics, keyMap, hasErrors, workspaceId, environmentId}` - the last two are the scope of the **connection** used; credential-looking inputs show `***` | `plan` | `baseWorkflowId` (when editing) | `{"plan":{...},"baseWorkflowId":456}` |
| `engini_workflows_get_workflow_plan` | Saved workflow as a plan (`s{N}` keys, opaque steps) + `revisionId`. Values are NOT redacted | `workflowId` | - | `{"workflowId":456}` |
| `engini_workflows_create_workflow_from_plan` | **Write.** Creates the workflow turned off, flagged AI-built. 201 `{workflowId, designerUrl, revisionId, diagnostics, workspaceId, environmentId}` | `plan` | `folderId` | `{"plan":{...},"folderId":789}` |
| `engini_workflows_update_workflow_from_plan` | **Write.** Full-graph update of a turned-off workflow, saved turned off. 200 `{workflowId, revisionId, diagnostics, workspaceId, environmentId}` | `workflowId`, `plan`, `expectedRevisionId` | - | `{"workflowId":456,"plan":{...},"expectedRevisionId":<revisionId from get_workflow_plan>}` |

Name lookups (read-only, used by the preflight to resolve a folder or workflow the user names):

| Slug | Arguments (all optional) | Returns |
|---|---|---|
| `engini_workflows_get_folders` | `name`, `type`, `createdAt`, `Filters` (`[{FieldName, Operator: IsEquals\|Contains, Value}]`), `SelectTop`, `Sorts` (`[{FieldName, Order: asc\|desc}]`) | `[{id, type, name, position, itemsCount, workspaceId, environmentId, createdAt, updatedAt}]` |
| `engini_workflows_get_workflows` | `name`, `folderName`, `folderId`, `workflowId`, `enabled`, `blocked`, `deleted`, `type`, `connectionId`, `createdBy`, `updatedBy`, `updatedAfter` / `updatedBefore`, `lastRunAfter` / `lastRunBefore`, `deletedAfter`, `updatedAt`, `lastRunAt`, `Filters`, `SelectTop`, `Sorts` | the workflows in the key's scope |

Pass the name the user gave (`{"name":"Invoices"}`), then match it yourself on the returned `name` (exact,
case-insensitive). Exactly one match -> use its id. Zero or several -> STOP, list the candidates, ask.

Notes:
- `designerUrl` is `<app>/workflows/{id}/edit`; it is null when the deployment has no client URL configured - then
  build it from the app host yourself and say so.
- `dependsOn` (options of a field that depends on another field) **cannot be sent** through the connector. Leave
  such fields for the user and list them in the proposal.
- `get_builder_tool_schema` with a `connectionId` and `get_builder_field_options` are rate-limited vendor reads: read
  each field once per run, not per repair round.
- **Table automations** (`plan-format.md` §1i): the catalog tools take no table yet, so they do not show the three
  Tables triggers (search returns none, the schema is `SLUG_NOT_FOUND`), and no tool lists the user's tables or a
  table's columns. Use the trigger slugs from §1i and ask the user for the table id and the column field names. A
  compile or create needs nothing more: `compile_workflow_plan` and the two writes accept `table` today. A table
  automation is reachable through the builder tools only: `get_workflows` and `get_workflow` do not return it, and
  enable, run and delete answer `404 NOT_FOUND` for it.

## 2. Other `engini_workflows` tools

| Slug | Flo may call it? |
|---|---|
| `engini_workflows_get_workflows`, `engini_workflows_get_workflow`, `engini_workflows_get_workflow_revisions`, `engini_workflows_get_folders`, `engini_workflows_get_connections` | Yes - read-only. `get_folders` gives a `folderId`; `get_workflows` is the dry-run "nothing was written" count |
| `engini_workflows_get_executions`, `get_execution`, `get_execution_log`, `get_execution_step_data` | Only if the user asks (they read the user's run data; never log values) |
| `engini_workflows_enable_or_disable_workflow` | **ONLY IF THE USER ASKS** for exactly this action on this workflow, in this conversation - never on Flo's own initiative, never to "finish the job". The user gets a permission prompt. A workflow Flo creates stays turned off |
| `engini_workflows_run_workflow`, `engini_workflows_rerun_execution` | **ONLY IF THE USER ASKS** (same rule) |
| `engini_workflows_delete_workflow` | **ONLY IF THE USER ASKS** (same rule) |

## 3. Errors and fixes

### 3a. HTTP refusals (`application/problem+json` `{status, code, path, message, fix, diagnostics?, currentRevisionId?}`)

| Status / code | Means | Do |
|---|---|---|
| 400 `SCOPE_REQUIRED` | Key not scoped to a workspace + environment. Writes always refuse an unscoped key; reads refuse only when no workspace resolves | STOP. Ask the user to issue a workspace-scoped key and re-create their connection with it. Never work around it |
| 403 `API_KEY_REQUIRED` | Caller is not a Developer API key (wrong auth method on the connection) | STOP. The connection must use auth method 1 (API key). Tell the user |
| 403 `PERMISSION_DENIED` | Key's user lacks `workspace.create.workflows` (or edit on that workflow) | STOP. Tell the user; their account admin grants it |
| 400 `INVALID_REQUEST` | Bad arg (missing `plan`, `field`, `connectionId`, `app`, bad `kind`, body > 1 MB, invalid JSON) | Fix the args per `path`/`message` |
| 404 `SLUG_NOT_FOUND` | Tool slug unknown/hidden for this account | Re-search the catalog; never guess a slug |
| 404 `CONNECTION_NOT_FOUND` | A named `connectionId` is not usable here | Re-list connections; use one from the list, or omit |
| 404 `NOT_FOUND` | Workflow/folder not in this scope or not readable | Check the id against `get_workflows`; a workflow in another workspace is invisible by design |
| 404 `UNKNOWN_FIELD` | Options asked for a non-dropdown field | Use a field from the schema's `dynamicFields` |
| 400 `OPTIONS_NOT_READONLY` | Field's options come from a source the builder will not run (a designer-local list, or a workflow the builder does not run) | Leave the field for the user; say so |
| 422 `PLAN_HAS_ERRORS` | A write refused: the plan has error diagnostics (listed). Nothing saved | Fix every error (compile again), then re-send. Never retry unchanged |
| 409 `WORKFLOW_ACTIVE` | Update refused: the workflow is on | STOP. Ask the user to turn it off, or offer a new turned-off copy (create) |
| 409 `REVISION_CONFLICT` | Saved since you read it (`currentRevisionId` given) | Re-read with `get_workflow_plan`, re-apply the change, compile, show the diff again, then update with the new `revisionId` |
| 400 `SAVE_REJECTED` | The designer's own save gates refused (connection ownership, schedule floor, AI tool names, ...) | Fix per `message`, compile, re-send once approved |
| 502 `VENDOR_ERROR` | The connected system failed during a read | Tell the user the connection may need re-authorizing; don't loop |
| 500 `INTERNAL_ERROR` | Server fault | Stop and report with the time; do not retry a write |

### 3b. Plan diagnostics (`{severity, code, stepKey, field, message}`)

Shape checks (nothing compiles until these are fixed):

| Code | Fix |
|---|---|
| `UNKNOWN_STEP_TYPE` | `type` must be one of the 12 in `plan-format.md` §0 |
| `INVALID_KEY` / `DUPLICATE_KEY` | Letter first, `[A-Za-z0-9_]`, ≤40, unique plan-wide |
| `MISSING_TRIGGER` / `NULL_STEP` | Add the trigger; remove null entries |
| `MISSING_CONDITION` / `UNKNOWN_OPERATOR` | `if` needs `condition.left` + `op` from `eq ne gt gte lt lte contains empty notempty` |
| `MISSING_ITEMS` | `foreach` needs `items` |
| `MISPLACED_BRANCH` | `then`/`else` only on `if`; `do` only on `foreach`/`do_while`/`scope`; `cases`/`default` only on `switch`; none of them, and no `onFailure`, on the trigger or an opaque step (to add a failure path to an opaque step, name its tool as an `action`) |
| `FAILURE_PATH_EMPTY` | `onFailure: []` - give it at least one step, or leave the member out |
| `SWITCH_VALUE_MISSING` | A `switch` needs the value it compares in `inputs.data` (usually a `{{ref}}`) |
| `SWITCH_CASES_MISSING` / `SWITCH_TOO_MANY_CASES` | 1-50 cases `[{value, steps}]`; for a yes/no choice use an `if`; for more, group values in an `if` or split the switch |
| `SWITCH_CASE_VALUE_MISSING` | Every case needs a `value` |
| `SWITCH_CASE_DUPLICATE` | Two cases with the same value text - only the last would run. Merge them or make the values distinct (`1` and `1.0` also match each other at run time) |
| `DO_WHILE_CONDITION_MISSING` | A `do_while` needs `condition` (`left` + `op`): without one it repeats to its limit and fails |
| `DO_WHILE_BODY_EMPTY` | A `do_while` needs at least one step in `do` |
| `INVALID_NOTE` | A note needs `content`; `id` 32 hex; `color` from the list; `x` with `y`; size in range (`plan-format.md` §1d) |

Compiler checks:

| Code | Sev. | Fix |
|---|---|---|
| `SLUG_NOT_FOUND` | error | Search the catalog; a block "not available" means the environment lacks it |
| `INVALID_TRIGGER` | error | Trigger is action-shaped (`tool`, no `type`) or `opaque` ref 1 |
| `KEY_COLLISION` | error | `s{N}` keys only for existing steps (opaque key must be `s{ref}`); trigger is step 1 |
| `OPAQUE_REF_NOT_FOUND` | error | `ref` must be an existing non-branch step; keep decompiled opaque steps as returned |
| `STEP_KIND_CHANGED` | error | Container <-> plain in place: new key instead |
| `CONTAINER_INCOMPLETE` | error | Container lacks a branch it should have: replace with a new key, or leave it for the designer |
| `NAME_REQUIRED` / `NAME_TOO_LONG` | error | Non-blank name ≤ 64 chars |
| `FOREIGN_CONNECTION` | error | Use an id from `list_builder_connections`, `auto` or `none` |
| `INVALID_CONNECTION` | error | `connection` is `auto`, `none` or a number |
| `UNKNOWN_INPUT` | error | Input names exactly as in the tool schema |
| `REFERENCE_IN_NOPARSE_FIELD` | error | That field is sent verbatim: literal value only |
| `UNKNOWN_REFERENCE` / `INVALID_REFERENCE` | error | Key must exist in the plan; path chars per `plan-format.md` §2 |
| `ITEM_OUTSIDE_LOOP` / `UNSUPPORTED_LOOP_ITEMS` | error | `.item` only inside its foreach; `items` must be one `{{key.path}}` |
| `UNPARSEABLE_CONTENT` / `CONTENT_NOT_LOADED` | error if the plan sets anything on the step, else warning | Leave the step's inputs out (keep it as is), or replace it under a new key; the user fixes it in the designer |
| `UNVERIFIED_INPUT` | warning | The request object is not picked yet; the user checks the field in the designer |
| `PICKER_CHANGED_FIELDS_CLEARED` | warning | The step now picks another object; set the fields the new object needs |
| `NEEDS_CUSTOMER_INPUT` | warning | A connection-dependent dropdown whose options can't be read (no connection); value kept with no label - the user completes it. Not raised for platform-block dropdowns |
| `UNKNOWN_OPTION` | warning | Value is not an option id (message lists up to 10). Use an id - treat as must-fix. Only when the list can decide it; see `OPTION_NOT_CHECKED` |
| `OPTION_NOT_CHECKED` | warning | The value matched no option, but the list cannot decide it (empty, multi-select, server-searched field, dependent list read for a non-literal parent). Value kept. Pick from `get_builder_field_options` if you can; otherwise name it in the proposal's Picks list |
| `QUERY_OPTION_NOT_ALLOWED` / `QUERY_OPTION_REQUIRED` | error | `filters`/`top`/`sorts` only where the schema's `query` offers them, `advancedFilter`/`offset` only on Sort & Filter; add the one it marks required |
| `INVALID_QUERY_FIELD` / `OPERATOR_NOT_ALLOWED` | error | Field from the object's filterable/sortable fields; operator from the tool's list (`plan-format.md` §1b) |
| `SUBITEM_NOT_ALLOWED` / `UNKNOWN_SUBITEM_FIELD` / `INVALID_SUBITEM_FIELD` / `TOO_MANY_SUBITEM_ROWS` | error | Only tables, names and row counts from the schema's `subItems` section (`plan-format.md` §1c) |
| `SUBITEMS_CLEARED` | warning | The edit omitted a step's tables - send back the ones from `get_workflow_plan` unless clearing is intended |
| `NOTE_CONTENT_TOO_LONG` / `TOO_MANY_NOTES` | error | Max 8,000 chars per note, 50 notes - only checked on notes the plan adds or changes |
| `NOTES_REPLACED` | warning | The `notes` array dropped stored notes (ids listed) - resend them unless removal is intended |
| `INVALID_TOP` / `INVALID_SORT_DIRECTION` / `TOO_MANY_QUERY_ROWS` | error | `top` ≥ 1, `offset` ≥ 0; `asc`/`desc`; within the tool's max filters/sorts |
| `FIELD_IS_NOT_A_FILTER` | warning | An object field written as an input picks nothing: move it to `filters` |
| `STEP_AFTER_FAILURE_HANDLER` | warning | The step runs only on failure of the handled step - move it if that wasn't meant |
| `FORK_EDGE_DROPPED` | warning | A moved step no longer runs alongside its fork siblings - confirm with the user |
| `FAILURE_PATH_NOT_MOVABLE` | error | An existing step heads an `onFailure` it is not already the handler of, moves to another container, or an existing failure-path step sits after a new one in an `onFailure`. A plan creates failure paths, never moves one or turns a step into a handler: give the handler a new key, add new steps after the existing handler, or leave the change to the designer |
| `FAILURE_PATH_OMITTED` | error | The plan keeps a step but leaves out its existing failure path (named in the message). Send it back exactly as `get_workflow_plan` returned it (nested under `onFailure`, or flat); removing it is a designer action |
| `FAILURE_PATH_FLAGS_KEPT` | warning | An existing failure handler (or a step that runs either way) is listed in an ordinary place; it keeps its role there. Put it back under its step's `onFailure` unless the user changes it in the designer |
| `FAILURE_PATH_OWN_OUTPUT` | warning | A failure-path step reads the failed step's output, which is missing or partial then: read an earlier step instead |
| `ERROR_TEXT_FORWARDED` | warning | A failure-path step sends `@@lasterror`/`@@lasterrormessage`/`@@errors` to a tool outside Engini - that text can be the failed step's whole request (URL, headers, body). Use a fixed message plus the run id; keep it only if the user chose it deliberately, and say so in the proposal |
| `SWITCH_CASE_VALUE_INVALID` | error | A case value holds markup (a script tag, an event handler, a `javascript:` link): remove it. Or the engine cannot parse it (it would never match): wrap a text value that starts with a digit, `.`, `-` or `+` and holds a space or comma in double quotes, `"\"1 - High\""` |
| `SWITCH_SHAPE_UNSUPPORTED` | error | The existing switch has a second Default or a non-Case branch, which a plan cannot describe: keep it `opaque` as `get_workflow_plan` returns it, or fix it in the designer |
| `DO_WHILE_LIMIT_INVALID` | error | `count` (1-5000) / `timeout` (1-60 minutes) must be a whole number in the block's range, never a reference; leave it out for the default |
| `DO_WHILE_CONDITION_STATIC` | warning | The condition reads no variable a `set_variable` inside `do` sets, so it never changes and the loop runs to its limit and fails. Set a variable in the loop and test it - treat as must-fix |
| `DO_WHILE_NO_OUTPUT` | warning | A step reads a `do_while`'s output; it has none (no current item). After the loop, read a variable the loop sets; inside the loop, an earlier step of `do` |
| `MAP_ARRAY_KEY_NORMALIZED` | warning | A Map Array column name had spaces, stored without them: read it as `{{map.TotalAmount}}`, and write names without spaces |
| `PARSE_JSON_SAMPLE_MISSING` | error | A new Parse JSON step needs a `sample` (so does changing `mapDictionary` when none is saved): a made-up JSON or XML document of the shape it parses - never a real record |
| `PARSE_JSON_SAMPLE_INVALID` | error | The sample is over 64 KB, over 64 levels deep, unreadable, holds a DTD/entity or markup, has no object, or too many objects/fields: cut it to the fields you read |
| `PARSE_JSON_ONLY_MEMBER` | error | `sample`/`mapDictionary` only on the built-in Parse JSON tool; raised on any other tool step (on a block they are ignored) |
| `PARSE_JSON_NO_DICTIONARY` | warning | `mapDictionary` is on but the sample has no object whose keys are numbers (ids): the step outputs the raw text or fails. Turn it off, or fix the sample |
| `ADVANCED_FILTER_OUTSIDE_DATA` | warning | An advanced filter's `field` does not start with the step's `data` reference, so it reads the whole output, the same for every record: write `{{<data ref>.<field>}}` |
| `SORT_FILTER_UNTYPED` | warning | A designer Sort & Filter's `data` is not another step as a whole (a path such as `{{s2.records}}`, an expression), so its filters and sorts compare as text: read the whole step (`{{s2}}`) or tell the user |
| `AI_AGENT_NOT_ALLOWED` | error | `model` / `memory` / `tools` only on an `ai_agent`; an `ai_agent` takes no `tool`, `condition` or `items` (`plan-format.md` §1e) |
| `AI_MODEL_REQUIRED` | error | A new `ai_agent` needs `model` `{provider, connection, inputs}` |
| `AI_MODEL_CONNECTION_REQUIRED` | error | Model `connection` is `none`/0, or `auto` finds none: give a connection id of the provider |
| `INVALID_AI_MODEL` | error | Provider not one of `openai anthropic claude gemini google azure_openai monday` (no `bedrock`), or no model on that connection's app - the message lists the accepted connection ids |
| `AI_MODEL_NAME_REQUIRED` | error | Set `model.inputs.model` to an option id from `get_builder_field_options` slug `model.{provider}` (not for `azure_openai`) |
| `AUTO_CONNECTION_UNPUBLISHED_APP` | warning | `auto` picked a connection on an unpublished app - give the published app's connection id |
| `INVALID_AI_MEMORY` | error | `memory` needs `sessionId`; `windowLength` 0-100 |
| `INVALID_AI_AGENT` | error | Literal `MaxIterations` outside 1-50 |
| `INVALID_AI_TOOL` | error | Tool `name` not `[a-z0-9_]` 1-128 / duplicate in the AI agent, no `tool`, or a description too long / multi-line / holding `{{` `##` `@@` or markup |
| `AI_TOOL_INPUT_CONFLICT` | error | Same field in a tool's `inputs` and `aiInputs`: pick one |
| `TOO_MANY_AI_TOOLS` | error | More than 50 tools on one agent |
| `AI_TOOL_NOT_ALLOWED` | error | Tool is not a plain connector action (block, container, AI Agents app action, authenticated HTTP), or an `aiInputs` field is a URL/host/credential: set it in `inputs` or on the connection |
| `AI_TOOL_FREEFORM_INPUT` | warning | The LLM fills a SQL/code/script/body field and can write anything there. **List every one in the proposal table** for the user to approve; recommend a read-only DB user |
| `AI_TOOLS_CLEARED` | warning | The edit left out `memory` or `tools` of an existing agent, so they were removed - resend them from `get_workflow_plan` unless removal is intended |
| `TABLE_NOT_FOUND` | error | `table` is not a table id, or not one of the user's tables in this workspace and environment. Ask the user for the id from the table's address (`plan-format.md` §1i); never guess one. The message's "GET catalog/tables" is not a builder tool yet |
| `TABLE_REQUIRED` | error | A Tables trigger needs `table`. On a create, add it. On an edit of an ordinary workflow it cannot be added: build a new table automation instead |
| `TABLE_NOT_ALLOWED` | error | `table` with a trigger that is not a Tables trigger (an edit whose kept `opaque` trigger is not one). Use a Tables trigger, or leave `table` out |
| `TABLE_NOT_CHANGEABLE` | error | The table is fixed at create: a different `table` on an edit, a `table` added to an ordinary workflow, or a trigger table input that differs from `table`. Leave `table` out on an edit (it keeps its table) and give the trigger no table input; to use another table, create a new workflow |

Validator checks:

| Code | Sev. | Fix |
|---|---|---|
| `TRIGGER_MISSING` / `TRIGGER_NOT_TRIGGER` | error | Step 1 must be a trigger tool |
| `STEP_DISCONNECTED` | error | Every step reachable from the trigger |
| `ACTIVITY_NOT_AVAILABLE` | error (warning on an unchanged step) | Activity not offered to this account: pick another tool |
| `REQUIRED_INPUT_MISSING` | error (warning on an unchanged step) | Set `inputs.<field>`; if the value is the user's to choose, ask the user |
| `ILLEGAL_ENUM_VALUE` | error (warning on an unchanged step) | Use one of the listed option ids |
| `FORWARD_REFERENCE` / `REFERENCE_NO_OUTPUT` | error | Reference only earlier steps that return data |
| `UNKNOWN_OUTPUT_PATH` | warning | Check the field name against the step's output schema |
| `VARIABLE_NOT_INITIALIZED` / `VARIABLE_REF_INVALID` | error | `init_variable` earlier on the path; `VARIABLE` = its key |
| `MISSING_CONNECTION` | warning | Step has no connection: the user connects it in the designer. Turning the workflow on is refused until then |

Other codes the validator can surface through compile (rare; report verbatim): `WORKFLOW_STEP_PARENT_NOT_CONTAINER`,
`WORKFLOW_STEP_PARENT_CYCLE`, `WORKFLOW_STEP_SELF_EDGE`, `WORKFLOW_CONTAINER_NOT_SUPPORTED`,
`WORKFLOW_CONTAINER_NOT_EMPTY`, `WORKFLOW_STEP_DYNAMIC_CONNECTION_INVALID`,
`WORKFLOW_STEP_DYNAMIC_CONNECTION_EXPRESSION_MISSING`, `WORKFLOW_STEP_BODY_MEMBER_UNKNOWN`.

n8n AI mapping (`plan-format.md` §1e): `chatTrigger` -> webhook trigger; `agent` -> `block.ai_agent`; `lmChat*` ->
`model.provider`; `memoryBufferWindow` -> `memory`; `*Tool` nodes -> `tools[]`; `$fromAI('x')` -> `aiInputs`.

## 4. CLI-level failures

- Exit 4 / unknown slug: the connector changed. Re-run `engini tools list --application engini_workflows` and adapt.
- A tool listed by the CLI that errors before reaching the API (bad wire shape, `plan` arriving as a string): stop and
  tell the user at once - it is an Engini-side fault to report to Engini support. Do not switch to curl or
  `SendApiRequest` with the user's key to work around it.
