# WhatsApp Business Cloud API

This preview supports three actions and one combined event trigger. Send Text posts a text message. Send Template posts an existing approved template with positional text body parameters. Reply uses a normalized inbound message's sender and message ID. The receiver emits inbound text messages and delivery statuses for one configured business phone.

## Receiver ownership

One active trigger owns the callback override for one Meta app and WhatsApp Business Account (WABA). The override affects the WABA, including its other phones. Use a dedicated WABA for this receiver. This first version routes only one configured phone. It acknowledges other phones and unsupported event types without running the flow. It cannot share one WABA receiver across flows. Both messages and statuses use the same trigger, with separate switches to select either event type.

Do not install this receiver on a WABA whose existing app-default routing serves other phones. Do not configure a higher-priority phone callback override. The integration refuses a different existing WABA override. It does not alter the app's webhook settings, subscribe an unconfigured app, remove unrelated app subscriptions or unsubscribe the WABA.

## Setup

1. Create and control a Meta business app, WABA and registered Cloud API business phone. Complete Meta's business verification, app review, production access and billing requirements for your account. These are external prerequisites.
2. Configure the app's WhatsApp `messages` webhook field and subscribe your app to your WABA. Keep a working app-default callback for recovery. The app and WABA must belong to your deployment's operator.
3. Set `LANGFLOW_WHATSAPP_APP_ID`, `LANGFLOW_WHATSAPP_WABA_ID`, `LANGFLOW_WHATSAPP_PHONE_ID`, `LANGFLOW_WHATSAPP_APP_SECRET` and `LANGFLOW_WHATSAPP_GRAPH_VERSION` in the API and worker processes. Choose a supported Graph version from Meta's current version schedule. The app secret remains in server secret storage. It never enters the flow or the connection dialog.
4. Configure `LANGFLOW_TRIGGER_INGRESS_ORIGIN` as the public HTTPS origin for this deployment. The resulting callback URL must contain at most 200 characters. Enable trigger ingress and the trigger workers using the existing deployment instructions.
5. Generate your app's system-user access token with `whatsapp_business_management` and `whatsapp_business_messaging`. Assign access to the WABA and phone. Create your own WhatsApp connection in Langflow. Validation calls Meta's token debugger and lists the WABA's phone IDs. It replaces caller-supplied identity and scope metadata with the verified app/WABA/phone binding and actual token expiry.
6. Enable background execution consent on the connection. Add the event trigger and choose messages, statuses or both. An optional sender number allowlist applies to inbound senders and status recipients. Empty allows every sender for the configured business phone. Enable the trigger. Langflow reserves the app/WABA receiver before installing its override.

Actions and push triggers support configured hosted and self-managed servers. This version does not support Desktop, headless execution, WhatsApp's on-premises API, Embedded Signup, shared callback routing or business-scoped user IDs. It does not download media. Unknown inbound message types are acknowledged without creating events.

## Delivery and conversation behavior

POST deliveries require Meta's HMAC-SHA256 signature over the original bytes with the app secret. GET verification requires the trigger's generated verification token and returns only the bounded numeric challenge. A challenge never creates an event or changes subscription state.

Accepted batches contain at most 256 records and 1 MiB of raw data. A malformed supported record rejects the batch before any item is admitted. Valid records become canonical source items. Message IDs and delivery status versions dedupe retries even when Meta rebatches a notification. HTTP 200 follows durable intake. The normalized event retains the verified WABA, phone, sender or status recipient, message ID, timestamp and text or status. It omits raw contacts, profile data, media URLs, error text and unknown fields. Known token forms and the signing secret are redacted from visible message text.

Conversation sessions use WABA, business phone and sender together. Inbound text and status updates for that sender use the same session. Reply verifies that the current connection targets the original business phone and posts the received message ID as context. A flow can still change its inputs, so this is routing context rather than proof of recipient consent.

Meta enforces the customer service window, approved template status, recipient consent, messaging eligibility, quality restrictions and rate limits. Operators remain responsible for obtaining consent and honoring opt-outs. This integration does not promise a message will be delivered when the send endpoint accepts it. Delivery status events provide the later result. It never retries a send automatically after an uncertain network failure, which could otherwise send twice. A user or flow retry can still duplicate an outbound message.

## Recovery and cleanup

System-user tokens have no automatic refresh here. Validation records Meta's actual expiry, including finite data-access expiry. A nonexpiring token is still revocable. Reconnect when it expires or is revoked, and keep the same app/WABA/phone binding. Rotate the server app secret together with Meta's configuration and restart processes using it. Pending callbacks will fail signature checks while the secrets disagree.

Disable a receiver and let durable cleanup finish before enabling it again or replacing it. Admission rejects a WABA with outstanding cleanup, including cleanup retained after a trigger is deleted. This prevents an old cleanup task from removing a replacement callback. Cleanup proves the original account, checks that the current WABA override still equals the recorded callback, and resets only that override to the app default. It leaves a replacement callback unchanged. Preserve the original app and account settings until cleanup completes. An operator changing callbacks externally can race the provider's read and write operations because Meta does not provide a conditional update in this contract.

Owner deletion can retain a sealed access token for this fixed cleanup operation until the shared retention deadline. It retains no refresh token and does not recreate the deleted connection. The sealed app, WABA, phone and callback binding must remain intact. Cleanup still verifies the token with Meta and checks WABA phone membership before resetting the original override. An expired, altered or policy-denied cleanup credential cannot authorize a provider request.

If Meta accepted an override but the response was lost, provisioning retries the reserved callback and verification token. It refuses another callback. The receiver has no expiry or renewal timer. External callback drift is not detected by periodic polling in this version. Check Meta's webhook dashboard and repair routing before re-enabling after external changes.

## Evidence and acceptance

The capability contract is recorded in [whatsapp.v1.json](contracts/whatsapp.v1.json). Tests cover synthetic Graph HTTP responses, installed bundle discovery, credential validation, database uniqueness, signature rejection, sender filtering, canonical batch dedupe, actual shared ingress, dispatch and durable cleanup. Live Meta account acceptance, end-to-end phone delivery and production limits remain unverified. Owner acceptance remains pending.

Official references include Meta's [current Cloud API collection](https://www.postman.com/meta/whatsapp-business-platform/collection/wlk6lh4/whatsapp-cloud-api), [callback override endpoint](https://www.postman.com/meta/whatsapp-business-platform/request/un84tul/override-callback-url), [token debugger](https://www.postman.com/meta/whatsapp-business-platform/request/i1mz7w8/debug-token), [send text endpoint](https://www.postman.com/meta/whatsapp-business-platform/request/8gvd47s/send-text-message), and [webhook verification guide](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/). The SDK is archived and is cited only for the signature and challenge protocol. Current developer documentation returned HTTP 429 during this investigation. No live acceptance claim is inferred from these references.
