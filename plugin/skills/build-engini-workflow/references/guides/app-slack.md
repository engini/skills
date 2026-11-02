# Slack

No verified builder quirks yet.

Unverified leads (slug `slack`, action-based, OAuth2):
- Search `{"q":"send message","app":"slack","kind":"action"}` and read the schema; never guess the channel field name.
- A channel input is most likely a dynamic dropdown: read its options through the step's connection and use the option id (channel id), not `#name`.
