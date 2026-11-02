# Email (Gmail / Outlook)

Verified (live test):
- Gmail `gmail.Send Email` needs `to`, `subject`, `body`; no dynamic fields.
- Outlook `outlook.send_email` also requires `frommailbox` (dynamic dropdown): read its options through the connection if possible, otherwise leave it for the user. `outlook.Send Email` is deprecated.
- A named connection is passed as its numeric id in a string: `"connection":"<connection id>"`.
- Gmail `Send Email` has no output (`REFERENCE_NO_OUTPUT` on `{{send.threadId}}`) but takes `threadId` (reply in thread). Gmail natively has only Send Email, ReadEmail (needs messageId), Get/Set Labels; there is no native thread or message lookup - tell the user rather than building one.
- Google Sheets `GetSheetOrCell` returns `values` as rows of cells, trailing empty cells dropped; `valueRenderOption` option id `FORMATTED_VALUE ` has a trailing space the plan trims (`UNKNOWN_OPTION`) - use `UNFORMATTED_VALUE`.

Unverified leads (confirm the slug in the catalog and the inputs in the live schema):
- Both have trigger `Check for new emails` and action `Send Email` with inputs `to`, `subject` (plain text) and `body` (rich text: references inline are fine).
- Outlook `Send Email` also has `Attachments` and `frommailbox` (dynamic list): read its options through the step's connection or leave it empty.
- Attachments need the `Initialize attachment array` / `append to attachments array` helper actions - flag to the user rather than building them blind.
