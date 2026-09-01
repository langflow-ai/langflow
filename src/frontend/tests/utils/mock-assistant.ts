import type { Page, Route } from "@playwright/test";

const ASSISTANT_MODEL = {
  displayName: "gpt-4o-mini",
  id: "OpenAI-gpt-4o-mini",
  name: "gpt-4o-mini",
  provider: "OpenAI",
};

const COMPONENT_CODE = `from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema import Message


class UppercaseText(Component):
    display_name = "Uppercase Text"
    description = "Returns the supplied text in uppercase."
    icon = "CaseUpper"

    inputs = [
        MessageTextInput(name="input_value", display_name="Text"),
    ]
    outputs = [
        Output(display_name="Message", name="message", method="build_output"),
    ]

    def build_output(self) -> Message:
        return Message(text=self.input_value.upper())
`;

function sse(...events: object[]): string {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
}

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    contentType: "application/json",
    status: 200,
  });
}

export type AssistantMockController = {
  armSessionReset: () => Promise<void>;
  releaseCancelledRequest: () => void;
  waitForSessionReset: () => Promise<URL>;
};

/**
 * Install deterministic browser-level contracts for the Assistant's model
 * catalog, SSE transport, session reset, and generated-component validation.
 */
export async function mockAssistant(
  page: Page,
): Promise<AssistantMockController> {
  await page.addInitScript((model) => {
    window.localStorage.setItem(
      "langflow-assistant-selected-model",
      JSON.stringify(model),
    );
  }, ASSISTANT_MODEL);

  await page.route("**/api/v1/models**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/enabled_models")) {
      await fulfillJson(route, {
        enabled_models: { OpenAI: { "gpt-4o-mini": true } },
        enabled_models_by_type: {
          OpenAI: { llm: { "gpt-4o-mini": true } },
        },
      });
      return;
    }

    if (/\/api\/v1\/models\/?$/.test(url.pathname)) {
      await fulfillJson(route, [
        {
          icon: "OpenAI",
          is_configured: true,
          is_enabled: true,
          models: [
            {
              metadata: { model_type: "llm" },
              model_name: "gpt-4o-mini",
            },
          ],
          provider: "OpenAI",
        },
      ]);
      return;
    }

    await route.fallback();
  });

  let releaseCancelledRequest = () => {};
  let cancelledRequestGate = new Promise<void>((resolve) => {
    releaseCancelledRequest = resolve;
  });
  let resolveSessionReset: (url: URL) => void = () => {};
  const sessionResetGate = new Promise<URL>((resolve) => {
    resolveSessionReset = resolve;
  });
  await page.exposeFunction("__recordAssistantSessionReset", (url: string) => {
    resolveSessionReset(new URL(url));
  });

  await page.route("**/api/v1/agentic/assist/stream", async (route) => {
    const requestBody = route.request().postDataJSON() as {
      input_value?: string;
    };
    const input = requestBody.input_value ?? "";

    if (input.includes("2000-word essay")) {
      await cancelledRequestGate;
      cancelledRequestGate = Promise.resolve();
      try {
        await route.fulfill({
          body: sse({
            event: "cancelled",
            message: "Cancelled by deterministic test fixture",
          }),
          contentType: "text/event-stream",
          status: 200,
        });
      } catch {
        // The browser aborts this request when Stop is clicked. Releasing the
        // gate only ensures the route handler cannot leak into the next test.
      }
      return;
    }

    const wantsComponent = /create\s+(?:a\s+)?(?:simple\s+)?component/i.test(
      input,
    );
    const body = wantsComponent
      ? sse({
          event: "complete",
          data: {
            class_name: "UppercaseText",
            component_code: COMPONENT_CODE,
            duration_seconds: 0.01,
            result: "The deterministic component is ready for approval.",
            usage: { input_tokens: 8, output_tokens: 12, total_tokens: 20 },
            validated: true,
            validation_attempts: 1,
          },
        })
      : sse(
          { event: "token", chunk: "Langflow is a deterministic " },
          { event: "token", chunk: "visual workflow builder." },
          {
            event: "complete",
            data: {
              duration_seconds: 0.01,
              result: "Langflow is a deterministic visual workflow builder.",
              usage: { input_tokens: 6, output_tokens: 7, total_tokens: 13 },
              validated: false,
            },
          },
        );

    await route.fulfill({
      body,
      contentType: "text/event-stream",
      headers: { "cache-control": "no-cache" },
      status: 200,
    });
  });

  await page.route("**/api/v1/custom_component", async (route) => {
    await fulfillJson(route, {
      data: {
        base_classes: ["Message"],
        description: "Returns the supplied text in uppercase.",
        display_name: "Uppercase Text",
        documentation: "",
        icon: "CaseUpper",
        outputs: [
          {
            display_name: "Message",
            method: "build_output",
            name: "message",
            types: ["Message"],
            value: "__UNDEFINED__",
          },
        ],
        template: {
          input_value: {
            display_name: "Text",
            name: "input_value",
            required: false,
            type: "str",
            value: "",
          },
        },
      },
      type: "UppercaseText",
    });
  });

  return {
    armSessionReset: async () => {
      await page.evaluate(() => {
        const assistantWindow = window as typeof window & {
          __assistantSessionResetMockInstalled?: boolean;
          __recordAssistantSessionReset: (url: string) => Promise<void>;
        };
        if (assistantWindow.__assistantSessionResetMockInstalled) {
          return;
        }

        const originalFetch = window.fetch.bind(window);
        window.fetch = async (input, init) => {
          const inputUrl =
            typeof input === "string"
              ? input
              : input instanceof URL
                ? input.href
                : input.url;
          const url = new URL(inputUrl, window.location.origin);
          const method = (
            init?.method ?? (input instanceof Request ? input.method : "GET")
          ).toUpperCase();
          if (
            method === "POST" &&
            url.origin === window.location.origin &&
            url.pathname === "/api/v1/agentic/sessions/reset"
          ) {
            await assistantWindow.__recordAssistantSessionReset(url.toString());
            return new Response(JSON.stringify({ status: "ok" }), {
              headers: { "content-type": "application/json" },
              status: 200,
            });
          }
          return originalFetch(input, init);
        };
        assistantWindow.__assistantSessionResetMockInstalled = true;
      });
    },
    releaseCancelledRequest,
    waitForSessionReset: () => sessionResetGate,
  };
}
