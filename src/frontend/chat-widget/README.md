# @langflow/chat-widget

React wrapper for the Langflow embedded chat web component.

## Install

```bash
npm install @langflow/chat-widget
```

## Basic Usage

```tsx
import { LangflowChat } from '@langflow/chat-widget';

export function App() {
  return (
    <LangflowChat
      hostUrl="https://your-langflow.example.com"
      flowId="your-flow-id"
      apiKey={process.env.REACT_APP_LANGFLOW_KEY ?? ''}
      title="Support Assistant"
      placeholder="Ask me anything…"
    />
  );
}
```

### Required props

| Prop | Description |
| --- | --- |
| `hostUrl` | Base URL where Langflow is running (e.g. `http://localhost:7860`). |
| `flowId` | Flow ID or published endpoint name. |
| `apiKey` | Langflow API key (from **Settings → API Keys**, format `sk-…`). |

Optional props such as `chatPosition`, `chatWindowHeight`, `chatTriggerStyle`, etc. are forwarded directly to the underlying `langflow-chat` custom element (from the [`langflow-embedded-chat` repository](https://github.com/langflow-ai/langflow-embedded-chat#configuration)).

## Environment tips

- Set `REACT_APP_LANGFLOW_URL`, `REACT_APP_FLOW_ID`, and `REACT_APP_LANGFLOW_KEY` in `.env` and restart the dev server.
- Your Langflow flow must have both **Chat Input** and **Chat Output** components connected, and the LLM component inside the flow uses its own provider key (OpenAI, Anthropic, etc.).

## Troubleshooting

- **HTTP 403**: Langflow didn’t receive a valid API key – make sure you’re using the Langflow key (`sk-lf…` or `sk-MBX…`).
- **404 `/api/v1/run/`**: Flow ID missing or incorrect.
- **CORS**: configure `LANGFLOW_CORS_ORIGINS` on the Langflow server if your app runs on a different domain.

