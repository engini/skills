# Recipes - starter plans

Each recipe is tagged **verified** or **unverified**. An unverified recipe is a starting shape written against the
plan format, not a compiled result: compile it before relying on it, and fix what the diagnostics say.

`<...>` placeholders are slugs, ids or option ids you must read from the catalog, schema or options for THIS account.
`builtin_tools.Button` is the manual-start trigger (verified in R3).

## R1. Manual start, variable, wait, stop - unverified - compile pending

```json
{
  "name": "Flo R1 - variable and delay",
  "trigger": { "key": "start", "tool": "builtin_tools.Button" },
  "steps": [
    { "key": "counter", "type": "init_variable",
      "inputs": { "NAME": "counter", "TYPE": "<VARTYPE option id, e.g. integer>", "VALUE": "0" } },
    { "key": "bump", "type": "set_variable", "inputs": { "VARIABLE": "counter", "VALUE": "1" } },
    { "key": "wait", "type": "delay", "inputs": { "COUNT": "5", "UNIT": "<UNIT option id, e.g. 1 = Minute>" } },
    { "key": "done", "type": "stop", "inputs": { "status": "<status option id, e.g. 1 = Success>" } }
  ]
}
```

## R2. Branch on a value - unverified - compile pending

```json
{
  "name": "Flo R2 - if / else",
  "trigger": { "key": "start", "tool": "builtin_tools.Button" },
  "steps": [
    { "key": "flag", "type": "init_variable",
      "inputs": { "NAME": "flag", "TYPE": "<VARTYPE option id, e.g. string>", "VALUE": "yes" } },
    { "key": "check", "type": "if",
      "condition": { "left": "{{flag}}", "op": "eq", "right": "yes" },
      "then": [ { "key": "ok", "type": "stop", "inputs": { "status": "<status option id, e.g. 1 = Success>" } } ],
      "else": [ { "key": "fail", "type": "stop", "inputs": { "status": "<status option id, e.g. 2 = Failure>" } } ] }
  ]
}
```

Checks: the variable reference form `{{flag}}` (no path) is itself unverified - if it compiles to
`UNKNOWN_OUTPUT_PATH`/`REFERENCE_NO_OUTPUT`, tell the user and leave the condition for the designer.

## R3. Send an email - verified (compiles clean)

```json
{
  "name": "Flo R3 - send an email",
  "trigger": { "key": "start", "tool": "builtin_tools.Button" },
  "steps": [
    { "key": "mail", "tool": "<gmail or outlook slug>.Send Email", "connection": "auto",
      "inputs": { "to": "<address the user gave>", "subject": "Hello from Flo",
                  "body": "Started at @@utcnow()" } }
  ]
}
```

Verified plan (`builtin_tools.Button` is the manual trigger; Gmail send is `gmail.Send Email`; Outlook is
`outlook.send_email` - `outlook.Send Email` is deprecated):

```json
{"name":"...","trigger":{"key":"start","tool":"builtin_tools.Button"},"steps":[{"key":"mail","tool":"gmail.Send Email","connection":"<id>","inputs":{"to":"...","subject":"...","body":"..."}}]}
```

Expect `MISSING_CONNECTION` (warning) when the account has no mail connection. The `@@utcnow()` in the body above is
a known issue, see `expressions.md` Functions.

## R4. Loop over a list - unverified - compile pending

```json
{
  "name": "Flo R4 - for each item",
  "trigger": { "key": "start", "tool": "builtin_tools.Button" },
  "steps": [
    { "key": "items", "tool": "<monday slug>.Get Items", "connection": "<monday connection id>",
      "inputs": { "BOARD_ID": "<board option id>" } },
    { "key": "each", "type": "foreach", "items": "{{items.<list field from the output schema>}}",
      "do": [
        { "key": "note", "tool": "<monday slug>.Create Item Update", "connection": "<monday connection id>",
          "inputs": { "ITEMID": "{{each.item.<id field>}}", "BODY": "Checked by Flo: {{each.item.<name field>}}" } }
      ] }
  ]
}
```

`Get Items`' input names are not in this file on purpose: read them from its schema.

## R5. Count inside a loop - unverified - compile pending

```json
{
  "name": "Flo R5 - count rows",
  "trigger": { "key": "start", "tool": "<trigger slug that returns a list>" },
  "steps": [
    { "key": "total", "type": "init_variable",
      "inputs": { "NAME": "total", "TYPE": "<VARTYPE option id, e.g. integer>", "VALUE": "0" } },
    { "key": "each", "type": "foreach", "items": "{{start.<list field>}}",
      "do": [
        { "key": "add", "type": "set_variable",
          "inputs": { "VARIABLE": "total", "VALUE": "@@add({{total}}, 1)" } }
      ] }
  ]
}
```

`set_variable` is shown for the shape; the platform also has an `Increment Variable` action (search it) that may be the
better fit.

## R6. One object variable instead of many - unverified live

Twenty values the run needs later go into **one** `init_variable` with a `value` tree, not twenty variables. Needs a
server whose `block.init_variable` schema carries `manualValue` (`plan-format.md` §1f) - without it, `value` is
dropped silently.

```json
{
  "name": "Flo R6 - one object variable",
  "trigger": { "key": "deal", "tool": "<trigger slug>" },
  "steps": [
    { "key": "ctx", "type": "init_variable",
      "inputs": { "NAME": "ctx", "TYPE": "object" },
      "value": {
        "customer": { "name": "{{deal.<name field>}}", "amount": "{{deal.<amount field>}}", "since": "2027-01-31" },
        "lines": [ { "sku": "A-1", "qty": 2 }, { "sku": "B-7", "qty": 1 } ],
        "vip": true,
        "note": "Deal {{deal.<name field>}} closed"
      },
      "valueTypes": { "/customer/amount": "number", "/customer/since": "date" } }
  ]
}
```

`amount` holds a reference, so it needs `valueTypes` to be a number; `since` needs it to be a date. `note` compiles to
`@@concat(...)`. With `{{deal.Name}}` / `{{deal.Amount}}` on a Salesforce opportunity trigger this compiles with 0
diagnostics (unverified live).

## R7. Catch a failure - unverified live

A failure path on one step, and try/catch around a group (`plan-format.md` §1h). The handler sends a **fixed message
plus the run id**, never `@@lasterrormessage()` (that can be the failed step's whole request - URL, headers, body).
A caught failure makes the run report **Success**, so the handler is the only place anyone hears of it: always notify.

```json
{
  "name": "Flo R7 - catch a failure",
  "trigger": { "key": "start", "tool": "<trigger slug>" },
  "steps": [
    { "key": "push", "tool": "<action slug>", "connection": "<connection id>", "inputs": { "id": "{{start.<id field>}}" },
      "onFailure": [
        { "key": "push_alert", "tool": "<email or chat action slug>", "connection": "<connection id>",
          "inputs": { "<message field>": "Push failed in run @@getworkflowhistoryid()" } } ] },
    { "key": "sync", "type": "scope",
      "do": [
        { "key": "read", "tool": "<action slug>", "connection": "<connection id>", "inputs": {} },
        { "key": "write", "tool": "<action slug>", "connection": "<connection id>", "inputs": { "<field>": "{{read.<field>}}" } }
      ],
      "onFailure": [
        { "key": "sync_alert", "tool": "<email or chat action slug>", "connection": "<connection id>",
          "inputs": { "<message field>": "The sync failed in run @@getworkflowhistoryid()" } },
        { "key": "sync_stop", "type": "stop", "inputs": { "status": "<status option id, e.g. 2 = Failure>" } } ] }
  ]
}
```

`sync_stop` ends the run as Failure after the alert, when the user wants the history to show it. A plan can add a
failure path, never move or delete an existing one.

## R8. Route on a value (switch) - unverified live

```json
{
  "name": "Flo R8 - switch",
  "trigger": { "key": "start", "tool": "<trigger slug>" },
  "steps": [
    { "key": "route", "type": "switch", "inputs": { "data": "{{start.<status field>}}" },
      "cases": [
        { "value": "new", "steps": [ { "key": "welcome", "tool": "<action slug>", "connection": "<connection id>", "inputs": {} } ] },
        { "value": "won", "steps": [ { "key": "invoice", "tool": "<action slug>", "connection": "<connection id>", "inputs": {} } ] }
      ],
      "default": [] }
  ]
}
```

1-50 cases with distinct values; `default` runs when none matches and may stay empty. Two outcomes are an `if`.

## R9. Poll until done (do_while) - unverified live

```json
{
  "name": "Flo R9 - poll until done",
  "trigger": { "key": "start", "tool": "<trigger slug>" },
  "steps": [
    { "key": "state", "type": "init_variable",
      "inputs": { "NAME": "state", "TYPE": "<VARTYPE option id, e.g. string>", "VALUE": "pending" } },
    { "key": "poll", "type": "do_while",
      "condition": { "left": "{{state}}", "op": "ne", "right": "done" },
      "inputs": { "count": "20", "timeout": "10" },
      "do": [
        { "key": "check", "tool": "<status action slug>", "connection": "<connection id>", "inputs": {} },
        { "key": "keep", "type": "set_variable", "inputs": { "VARIABLE": "state", "VALUE": "{{check.<status field>}}" } },
        { "key": "pause", "type": "delay", "inputs": { "COUNT": "1", "UNIT": "<UNIT option id, e.g. 1 = Minute>" } }
      ] }
  ]
}
```

The condition is checked before each pass, against variables and steps before the loop only: it reads `state`, which
the body sets. A condition on `{{check.status}}` would never change (`DO_WHILE_CONDITION_STATIC`). The loop has no
output: later steps read `{{state}}`, not `{{poll...}}`.

## R10. Sort, filter and reshape a list - unverified - compile pending (slugs verified)

```json
{
  "name": "Flo R10 - sort & filter, map array",
  "trigger": { "key": "start", "tool": "<trigger slug that returns a list>" },
  "steps": [
    { "key": "big", "tool": "builtin_tools.Sort & Filter", "connection": "none",
      "inputs": { "data": "{{start.<list field>}}" },
      "filters": [ { "field": "<field>", "operator": "eq", "value": "open" } ],
      "sorts": [ { "field": "<field>", "direction": "asc" } ], "top": 10 },
    { "key": "rows", "tool": "builtin_tools.MapArray", "connection": "none",
      "inputs": { "data": "{{big}}" },
      "subItems": { "properties": { "Customer": "{{big.<name field>}}", "Total": "{{big.<amount field>}}" } } }
  ]
}
```

A plan-built Sort & Filter compares values as **text**: prefer text filters (`eq`, `contains`), and tell the user a
numeric or date filter/sort needs the data object picked on the step in the designer. Map Array column names have no
spaces; later steps read `{{rows.Customer}}`. Map the Sort & Filter's output (`{{big}}`), not the trigger's list, or
the filter, sort and `top` are ignored; each per-row field is the `data` reference plus the field (`{{big.<field>}}`).

## R11. Parse a JSON payload - unverified - compile pending (slug verified)

```json
{
  "name": "Flo R11 - parse json",
  "trigger": { "key": "hook", "tool": "<webhook trigger slug>" },
  "steps": [
    { "key": "pj", "tool": "builtin_tools.Parse JSON", "connection": "none",
      "inputs": { "content": "{{hook.<body field>}}" },
      "sample": "{\"customer\": {\"name\": \"Sample Name\", \"email\": \"name@example.com\"}, \"total\": 1}" },
    { "key": "mail", "tool": "<email action slug>", "connection": "<connection id>",
      "inputs": { "to": "{{pj.customer.email}}", "subject": "Thanks, {{pj.customer.name}}" } }
  ]
}
```

The `sample` is **invented**: it is stored in clear text with the workflow, so never paste a real record the user
shows you - keep its field names, replace every value.
