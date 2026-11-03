# Platform blocks

Blocks are typed plan steps with **no `tool`** - the compiler resolves `block.<type>` on the platform built-ins app
("Built-in Tools", app slug `builtin_tools`). Read each block's fields and option ids live before use:
`get_builder_tool_schema` with `kind: "block"` and slug `block.<type>`, or `get_builder_field_options`. The ids below
are the values the platform ships; the live schema wins if they differ.

| `type` | Plan members | Inputs | Verified from |
|---|---|---|---|
| `if` | `condition`, `then`, `else` | none (the condition is not an input) | compile |
| `foreach` | `items`, `do` | none (`items` becomes the `data` input) | compile |
| `init_variable` | `inputs`, or `inputs` + `value`/`valueTypes` for an object/array (`plan-format.md` §1f) | `NAME` text, `TYPE` option id, `VALUE` (not with `value`) | compile + schema |
| `set_variable` | `inputs` | `VARIABLE` = the init step's key, `VALUE` | compile + schema |
| `delay` | `inputs` | `COUNT` (default `1`), `UNIT` option id | schema (unverified live) |
| `stop` | `inputs` | `status` option id (default `1`) | schema (unverified live) |
| `switch` | `cases`, `default` | `data` = the value compared (usually a `{{ref}}`) | compile (unverified live) |
| `do_while` | `condition`, `do` | optional `count` (most passes, default `100`), `timeout` (minutes, default `5`) | compile (unverified live) |
| `scope` | `do` | none | compile (unverified live) |

Built-in tools that are plain `action` steps (a `tool` slug from `search_builder_catalog`, app `builtin_tools`,
`connection: "none"`), not blocks - `plan-format.md` §1g has their members:

| Tool (slug) | Plan members | Output |
|---|---|---|
| Sort & Filter (`builtin_tools.Sort & Filter`) | `inputs.data` (the list), `filters`, `sorts`, `top`, `advancedFilter`, `offset` | the kept records: `{{sf.<field>}}` (fields not checked) |
| Map Array (`builtin_tools.MapArray`) | `inputs.data` (the list), `subItems.properties` (one row: output column -> value) | a list with one field per column: `{{map.<Column>}}` |
| Parse JSON (`builtin_tools.Parse JSON`) | `inputs.content` (the text to parse), `sample`, optional `mapDictionary` | the fields of `sample`: `{{pj.<field>}}` |

Option ids (confirm live):
- `TYPE` (VARTYPE): `string`, `integer`, `numeric`, `bool`, `datetime`, `array`, `object`. **Not** `Text`/`String`.
  Required. A label (`Text`, `Number`) or an empty TYPE is a compile **error** (`ILLEGAL_ENUM_VALUE` /
  `REQUIRED_INPUT_MISSING`); an id matched case-insensitively (`Integer`) is stored as the id.
- `UNIT` (SCHEDULE_FREQUENCY): `1` Minute, `2` Hour, `3` Day, `4` Week, `5` Month. Required (an empty UNIT is an error).
- `status` (TERMINATE_STATUS): `1` Success, `2` Failure, `7` Fell By Condition.

Rules:
- `if` gets exactly one Yes and one No branch from the platform; `then`/`else` fill them. An empty `else` is fine.
- `switch` compares `inputs.data` with each case's `value`: `cases` is `[{"value": ..., "steps": [...]}]`, 1-50 cases,
  first case first, each value a distinct literal or a `{{ref}}`. `default` runs when no case matches; the switch always
  gets a Default branch, so an empty or missing `default` is fine. Two cases with the same text are refused (only the
  last would ever run); values such as `1` and `1.0` also match each other at run time, so keep values distinct. The
  engine reads each value as an expression: a text value that starts with a digit, `.`, `-` or `+` and holds a space
  or comma (`1 - High`, `1,000`, `3.5 GHz`) must be wrapped in double quotes (`"value": "\"1 - High\""`), or it is
  `SWITCH_CASE_VALUE_INVALID` (unquoted it would never match).
- `do_while` repeats `do` while `condition` (an `if`'s condition) holds, **checked before each pass**: the body may run
  zero times. Each pass, the condition sees only variables and the steps before the loop, never the steps inside it:
  set a variable inside `do` and test that variable (`DO_WHILE_CONDITION_STATIC` otherwise - the loop would run to its
  limit and fail). A `do_while` has no current item and no output (`DO_WHILE_NO_OUTPUT`). `count` (1-5000) and
  `timeout` (1-60 minutes) are whole numbers, never a reference; leave them out for the defaults.
- `scope` groups steps in `do`. An error inside the group fails the Scope itself, so `onFailure` on a Scope is
  try/catch for the whole group.
- **`onFailure`** (any step but the trigger and an `opaque` step) is a chain that runs when that step fails. It sits
  beside the step in the same container, not inside it: its first step runs only on failure, the rest follow it. The
  canonical handler sends a **fixed message plus the run id** - never `@@lasterrormessage()` / `@@lasterror()` /
  `@@errors(N)`: that text can be the failed step's whole request (URL, headers and body), and it is the run's last
  error, not necessarily this step's. If the user wants the error text, a shorter form is the error's `Title`
  (`@@getproperty(@@lasterror(),"Title")`): the step's error message, not its request, but it can still hold the
  vendor's response text. Forwarding it outside Engini is the user's deliberate choice (`ERROR_TEXT_FORWARDED`). The failed step's
  own output is missing or partial there (`FAILURE_PATH_OWN_OUTPUT`).
- **A caught failure makes the whole run report Success.** Nobody learns of the failure unless the handler tells
  them: put a notify step (email, Slack, ...) inside every `onFailure`, and say so in the proposal.
- A plan can **add** a failure path and **edit** the steps on one; it cannot move or delete an existing one
  (`FAILURE_PATH_NOT_MOVABLE`, `FAILURE_PATH_FLAGS_KEPT`) - that stays a designer action. When you rewrite a step,
  send its `onFailure` back as `get_workflow_plan` returned it: leaving it out is `FAILURE_PATH_OMITTED`. An existing
  failure-path step can only head its own step's `onFailure`; add new steps after it, never before it.
- `set_variable` before (on no path after) its `init_variable` is `VARIABLE_NOT_INITIALIZED`.
- Steps inside `then`/`else`/`do`/a case/`default` see the steps before the block and the blocks they sit in, not
  another branch. A step on a failure path also sees the failed step and the steps before it.
- The trigger is never a block. Platform triggers: `builtin_tools.Button` (manual start, verified) and
  `builtin_tools.Schedule` (search with `kind: "trigger"` to confirm). Set the schedule with the trigger's `schedule`
  member (`plan-format.md` §1a) when the trigger's schema offers it; otherwise the user sets it in the designer.

Not buildable from a plan: Query Array (the catalog does not offer it - tell the user to add it in the designer).
Case and Default are never steps of their own: they are a `switch`'s `cases` and `default`. Not blocks: `http`,
`ai_step`. Other platform actions (Append To Array Variable, Increment Variable, Delay until, RunWorkflow, ...) are
ordinary `action` steps with a `tool` slug from the catalog - search for them.
