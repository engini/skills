# Monday.com

Pick the board first (applies to any step with an object picker; Monday is the example):
- A schema that lists the input in `objectPickers` (e.g. `BOARD_ID` on `monday.Create Item`) shows no column fields until the object is picked. Pick the board with the user, then re-read: `engini workflows schema <slug> --kind action --connection <id> --selected BOARD_ID=<board id>` (`--selected` is repeatable and needs `--connection`).
- The re-read lists that board's columns as inputs keyed by COLUMN ID (`status`, `text_mm3hsj6s`). Use those ids as input keys, never the column title - a title key compiles as `UNKNOWN_INPUT`.
- A status or dropdown column carries an `enum` of its visible option labels. Use only those labels as the value, exactly as returned; never invent or translate one.
- `unresolvedPicks` non-empty (`not_found` / `read_failed`; the answer is still HTTP 200) = the board was not read: stop and tell the user, do not guess columns. A `{{ref}}` pick resolves nothing.

Unverified leads (confirm the slug in the catalog and the inputs in the live schema):
- Triggers include `Item Created`, `Item Updated`, `Item Deleted`, `SubItem Created`; actions include `Create Item`, `Update Item`, `Create Item Update`, `Get Items`, `Get Items By Column Value`, `Move Item to Group`.
- `Create Item` / `Item Created`: `BOARD_ID` is an object picker (list BOARD) - it selects the request object, so column fields stay `UNVERIFIED_INPUT` until it holds a literal board option id.
- `GROUP_ID` (list GROUP) most likely depends on the board: needs `dependsOn`, which the connector cannot send - leave it for the user.
- `Create Item Update`: `ITEMID` + `BODY` (rich text) - references inline are fine.
