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

Option ids (confirm live):
- `TYPE` (VARTYPE): `string`, `integer`, `numeric`, `bool`, `datetime`, `array`, `object`. **Not** `Text`/`String`.
  Required. A label (`Text`, `Number`) or an empty TYPE is a compile **error** (`ILLEGAL_ENUM_VALUE` /
  `REQUIRED_INPUT_MISSING`); an id matched case-insensitively (`Integer`) is stored as the id.
- `UNIT` (SCHEDULE_FREQUENCY): `1` Minute, `2` Hour, `3` Day, `4` Week, `5` Month. Required (an empty UNIT is an error).
- `status` (TERMINATE_STATUS): `1` Success, `2` Failure, `7` Fell By Condition.

Rules:
- `if` gets exactly one Yes and one No branch from the platform; `then`/`else` fill them. An empty `else` is fine.
- `set_variable` before (on no path after) its `init_variable` is `VARIABLE_NOT_INITIALIZED`.
- Steps inside `then`/`else`/`do` see the steps before the block and the blocks they sit in, not the other branch.
- The trigger is never a block. Platform triggers: `builtin_tools.Button` (manual start, verified) and
  `builtin_tools.Schedule` (search with `kind: "trigger"` to confirm). Set the schedule with the trigger's `schedule`
  member (`plan-format.md` §1a) when the trigger's schema offers it; otherwise the user sets it in the designer.

Not buildable from a plan (no catalog kind - tell the user to add them in the designer): Switch/Case/Default,
Scope, Do While, Sort & Filter, Parse JSON, MapArray. Not blocks: `http`, `ai_step`. Other platform actions (Append
To Array Variable, Increment Variable, Delay until, RunWorkflow, ...) are ordinary `action` steps with a `tool` slug
from the catalog - search for them.
