# Priority (ERP)

No verified builder quirks yet.

Unverified leads (confirm the slug in the catalog and the inputs in the live schema):
- Built-in actions: `RunFormActivation`, `RunProcedure`; most Priority entity actions live on the connector - search `app: "<priority slug>"`.
- `RunFormActivation` inputs `formactivation` (list object FORM) and `activation` (list FORMACTIVATION_LIST): `activation` most likely depends on the chosen form, so its options need `dependsOn` - which the connector cannot send. Leave it for the user.
- Priority dropdown reads are vendor reads: read each once per run.
- The Priority app slug comes from `search_builder_catalog`, never from memory.
