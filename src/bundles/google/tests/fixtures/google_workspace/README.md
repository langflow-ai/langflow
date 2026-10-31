# Google Workspace response fixtures

These JSON bodies are **authored**, not captured. Each one follows the response or
error shape in Google's API reference for the method it stands in for (Gmail
`users.messages.send`, Drive `files.list`/`files.get`/`files.export`, Calendar
`events.list`/`events.insert`, and the Drive and Google API error pages), with
invented identifiers such as `message-0001` and `page-token-2`.

They pin the adapter's request shape and error mapping offline. They are not
evidence of how Google responds on a real account; that is what the opt-in live
suite in `tests/test_workspace_actions_live.py` is for. When a live run observes a
different shape, replace the fixture with the captured body (tokens and personal
data removed) and say so in the commit.
