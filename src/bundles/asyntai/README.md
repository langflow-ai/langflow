# lfx-asyntai

Asyntai AI Chatbot components as a standalone Langflow Extension Bundle.

[Asyntai](https://asyntai.com) is an AI chatbot for websites. It answers
visitor questions from the website's own pages and knowledge base, and it
collects leads. The bundle ships three components:

- `AsyntaiAskComponent` (**Asyntai AI Chatbot**): ask the chatbot a question and
  get the answer it gives from the website and knowledge base.
- `AsyntaiAddKnowledgeComponent` (**Asyntai Add Knowledge**): add a web page or
  a text to the chatbot's knowledge base.
- `AsyntaiLeadsComponent` (**Asyntai Leads**): list the email addresses and
  phone numbers that visitors left in the chat, as a table.

The components call the Asyntai REST API directly with `httpx` and need only a
user-supplied API key, so the bundle carries no vendor SDK dependency. See the
[Asyntai Langflow guide](https://asyntai.com/documentation/integrations/langflow/)
and the [API reference](https://asyntai.com/documentation/api-reference/).

## Install

```bash
pip install lfx-asyntai
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the components
appear in the palette's **Bundles** section under **Asyntai**.

## Configure

Set the **Asyntai API Key** input to a key from the Asyntai dashboard
(Settings -> API). The API is available on paid Asyntai plans. The components
do nothing until a key is supplied. The optional **Website** input takes a
website ID or a domain such as `example.com`; when it is empty, the primary
website of the account is used.

In tool mode, the components expose the tools `asyntai_ask_website`,
`asyntai_add_knowledge` and `asyntai_get_leads`.

## Develop

```bash
cd src/bundles/asyntai
pip install -e .
lfx extension validate src/lfx_asyntai
```

## Manifest

The extension manifest is shipped at `src/lfx_asyntai/extension.json` and
points at the bundle at `components/asyntai`. The components register under
the canonical namespaced IDs `ext:asyntai:<ClassName>@official`.
