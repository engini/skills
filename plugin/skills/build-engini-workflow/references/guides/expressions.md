# Expressions in plan syntax

In a plan you never write `##N`, badge HTML or `DisplayValue`: the compiler produces all of it.

## Two tokens

| Plan token | Compiles to | Example |
|---|---|---|
| `{{key.path}}` | `##<StepNo>.path` + a Dynamic Content badge | `{{deal.Amount}}` |
| `@@fn(args)` | the same function call, references inside rewritten | `@@toupper({{deal.Name}})` |

Everything else in a value is literal text. Literal HTML is always escaped and shown as text.

## Mixing text and references - let the compiler do it

Write plain text with references inline:

```json
"text": "Invoice {{invoice.IVNUM}} created for {{deal.Name}}"
```

For a plain (SimpleValue) field the compiler emits one `@@concat("Invoice ", ##3.IVNUM, " created for ", ##1.Name)`.
For rich-text fields it emits inline badges. Do not hand-write `@@concat` just to join text and references.

## Labels and option text: one `@@concat`, never `##a (##b)`

When you do build a composed value yourself (inside a function, or for a dynamic-list label), write ONE
`@@concat(...)`: `@@concat({{row.name}}, " (", {{row.id}}, ")")`. Text like `{{row.name}} ({{row.id}})` inside a
function argument context leaves a raw `##3.workflowId)` in the designer: the parser does not end a bare `##`
token at `)`.

## Loops

- `foreach.items` is ONE reference to a list: `"items": "{{get_rows.items}}"`. Not a function.
- Inside the loop's `do`, the current element is `{{loopKey.item}}`, a field of it `{{loopKey.item.sku}}`. It
  compiles to the list's path (`##2.items.sku`) - the engine rewrites that path to the current row. The loop's own
  step number never appears.
- `{{loopKey.item}}` outside its loop is `ITEM_OUTSIDE_LOOP`.
- Never index right after `item` (`item[0]`, `item.cells[1]`) - `LOOP_ITEM_INDEX`. Use
  `@@getarrayelement({{loopKey.item}}, 0)` (and `@@getproperty(..., "Field")` for a field of that element).
- Nested loops compose by path: inner `items: "{{outer.item.lines}}"`.

## Functions

- Use only names from the inventory below - never a function from memory. Names are lowercase; the badge label's
  casing in the designer is cosmetic.
- String literals: the parser has no escape. The compiler single-quotes a literal containing `"`; avoid literals
  with both quote kinds.
- Known issue: a zero-argument function such as `@@utcnow()` inside a rich-text input compiles to two function
  badges ("UtcNow(" and ")"). Tell the user to check it in the designer; do not claim it works.
- `@@workflowlastrundate()` is the scheduled-trigger watermark - use it, don't reimplement it with date math.
- A formula that compiles clean has still never run: say so in the proposal when a step depends on one.

Inventory by purpose:

| Purpose | Functions |
|---|---|
| **Text** | `concat` `contains` `startswith` `endswith` `length` `replace` `substring` `slice` `split` `indexof` `lastindexof` `nthindexof` `trim` `trimstart` `trimend` `toupper` `tolower` `char` `ascii` `newline` `carriagereturn` `linefeed` `tab` `striphtml` `createhtmllink` `reversehebrewtext` `priorityhebconvert` |
| **Logic** | `if` `switch` `and` `or` `not` `equal` `greater` `greaterorequal` `less` `lessorequal` `in` `isnull` `null` `stringisnullorempty` `tryparse` |
| **Number** | `add` `sub` `multiply` `divide` `mod` `power` `round` `roundup` `rounddown` `sum` `min` `max` `toint` `todecimal` `tobool` `stringtonumber` `randominteger` |
| **Date / time** | `utcnow` `localtimenow` `date` `datetime` `year` `month` `day` `hour` `minutes` `seconds` `dayofweek` `datediff` `addseconds` `addminutes` `addhours` `adddays` `addweeks` `addmonths` `addyears` `startofmonth` `endofmonth` `formatdatetime` `stringtodatetime` `converttolocaltime` `converttimezone` `converttounixdatetime` |
| **Array / object** | `createarray` `appendtoarray` `arraylength` `getarrayelement` `first` `last` `distinct` `join` `getproperty` `tojsonstring` `tostring` |
| **Encoding / hash** | `base64tostring` `stringtobase64` `urlencode` `urldecode` `encryptmd5` `encryptsha1` `encryptsha256` `encryptsha512` `tobinary` `readjwt` `guid` `randomstring` `getmimetype` |
| **Workflow context** | `workflow` `workflowlastrundate` `getworkflowhistoryid` `activitystatus` `errors` `lasterror` `lasterrormessage` `getuser` `filelength` |

Known arities (a wrong argument count fails at run time, not at compile):

| Call | Rule |
|---|---|
| `@@utcnow()` | exactly 0 args |
| `@@adddays(<date>, <n>[, <format>])` | 2 or 3 args; the optional third is a .NET format string applied to the result |
| `@@formatdatetime(<value>, <format>)` | exactly 2 |
| `@@if(<cond>, <then>, <else>)` | exactly 3 |
| `@@switch(<expr>, <case>, <result>[, ...][, <default>])` | 3 or more; pairs after the expression, and an **even** total means the last argument is the default |
| `@@concat(a, b, ...)` | 1 or more |
| `@@getproperty(<object>, <name>)` | 2, and arg 1 must resolve to an object |

A function not in the arity table: use it only in the shape its name makes unambiguous, and tell the user to check
the step in the designer.

## Conditions

`if.condition` operands are plain values with the same rules: `{"left":"{{deal.Stage}}","op":"eq","right":"Closed Won"}`.
`empty` / `notempty` ignore `right` (send `""`).

## Where references are refused

A NoParse field (or any input of a NoParseItems activity) is sent verbatim: a `{{...}}` there is
`REFERENCE_IN_NOPARSE_FIELD`. Use a literal, or another input of the tool.
