# Monday.com

No verified builder quirks yet.

Unverified leads (confirm the slug in the catalog and the inputs in the live schema):
- Triggers include `Item Created`, `Item Updated`, `Item Deleted`, `SubItem Created`; actions include `Create Item`, `Update Item`, `Create Item Update`, `Get Items`, `Get Items By Column Value`, `Move Item to Group`.
- `Create Item` / `Item Created`: `BOARD_ID` is an object picker (list BOARD) - it selects the request object, so column fields stay `UNVERIFIED_INPUT` until it holds a literal board option id.
- `GROUP_ID` (list GROUP) most likely depends on the board: needs `dependsOn`, which the connector cannot send - leave it for the user.
- `Create Item Update`: `ITEMID` + `BODY` (rich text) - references inline are fine.
