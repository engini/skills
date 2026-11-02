# Salesforce

No verified builder quirks yet.

Unverified leads (slug `salesforce`, object-based; confirm the slugs in the catalog and the inputs in the live schema):
- Triggers `RecordCreated`, `RecordUpdated`, `OutboundMessageWebhook`; actions `Create Record`, `Update Record`, `Delete Record`, `Get Record`, `Get Records` (slug `salesforce.<identifier>`).
- Each takes `sobject` (object picker, list SOBJECT_REQUEST): its value selects the request object. Until it is a literal option id the record fields are unknown -> `UNVERIFIED_INPUT` warnings. Read `sobject` options through the step's connection first, then the schema with that `connectionId`.
- Object-based: field names come from the picked sObject's schema on THAT connection - never from memory or another org.
