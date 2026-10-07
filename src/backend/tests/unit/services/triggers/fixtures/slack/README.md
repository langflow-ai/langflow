# Recorded Slack Events API bodies

Each file is one Events API request body, shaped as Slack documents it
(https://docs.slack.dev/apis/events-api/ and https://docs.slack.dev/reference/events).
A Socket Mode `events_api` envelope carries the same document as its `payload`,
so the cross-track contract tests wrap these same files rather than recording a
second set.

Identifiers are synthetic but keep Slack's shapes: team `T…`, app `A…`, users
`U…`, bots `B…`, channels `C…`/`G…`/`D…`. The verification `token` and
`event_context` fields Slack also sends are omitted: nothing reads them, and they
would only add high-entropy strings for the secret scanner to flag.
