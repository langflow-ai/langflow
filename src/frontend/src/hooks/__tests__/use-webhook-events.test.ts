import { cleanup, renderHook } from "@testing-library/react";
import { BASE_URL_API } from "@/customization/config-constants";
import { useWebhookEvents } from "../use-webhook-events";

type TestNode = { id: string; data?: { type?: string } | null };
type TestFlow = {
  id: string;
  data?: { nodes?: TestNode[] } | null;
};

let currentFlow: TestFlow | undefined;

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlow?: TestFlow }) => unknown) =>
    selector({ currentFlow }),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: { apiKey: null }) => unknown) =>
    selector({ apiKey: null }),
}));

jest.mock("@/stores/flowStore", () => ({ __esModule: true, default: {} }));

const eventSource = {
  addEventListener: jest.fn(),
  close: jest.fn(),
  onerror: null,
};
const createEventSource = jest.fn(() => eventSource);
const originalEventSource = Object.getOwnPropertyDescriptor(
  globalThis,
  "EventSource",
);

beforeEach(() => {
  jest.clearAllMocks();
  currentFlow = undefined;
  Object.defineProperty(globalThis, "EventSource", {
    configurable: true,
    value: createEventSource,
  });
});

afterEach(() => {
  cleanup();
  if (originalEventSource) {
    Object.defineProperty(globalThis, "EventSource", originalEventSource);
  } else {
    Reflect.deleteProperty(globalThis, "EventSource");
  }
});

it.each<TestFlow | undefined>([
  undefined,
  { id: "flow" },
  { id: "flow", data: null },
  { id: "flow", data: {} },
  { id: "flow", data: { nodes: [] } },
])("does not subscribe before webhook nodes are available: %j", (flow) => {
  currentFlow = flow;

  renderHook(() => useWebhookEvents());

  expect(createEventSource).not.toHaveBeenCalled();
});

it.each<TestNode>([
  { id: "InboundWebhookTrigger-1", data: { type: "InboundWebhookTrigger" } },
  { id: "NotWebhook-1", data: { type: "ChatInput" } },
  { id: "Webhook-1" },
  { id: "Webhook-1", data: null },
])("ignores a webhook-like node ID without a Webhook type: %j", (node) => {
  currentFlow = { id: "flow", data: { nodes: [node] } };

  renderHook(() => useWebhookEvents());

  expect(createEventSource).not.toHaveBeenCalled();
});

it("subscribes to a Webhook component regardless of its node ID", () => {
  currentFlow = {
    id: "flow",
    data: { nodes: [{ id: "custom-id", data: { type: "Webhook" } }] },
  };

  const { unmount } = renderHook(() => useWebhookEvents());

  expect(createEventSource).toHaveBeenCalledTimes(1);
  expect(createEventSource).toHaveBeenCalledWith(
    `${BASE_URL_API}webhook-events/flow`,
    { withCredentials: true },
  );
  unmount();
  expect(eventSource.close).toHaveBeenCalledTimes(1);
});

it("closes the subscription when the last Webhook component is removed", () => {
  const trigger = {
    id: "InboundWebhookTrigger-1",
    data: { type: "InboundWebhookTrigger" },
  };
  currentFlow = {
    id: "flow",
    data: {
      nodes: [trigger, { id: "Webhook-1", data: { type: "Webhook" } }],
    },
  };
  const { rerender } = renderHook(() => useWebhookEvents());
  expect(createEventSource).toHaveBeenCalledTimes(1);

  currentFlow = { id: "flow", data: { nodes: [trigger] } };
  rerender();

  expect(eventSource.close).toHaveBeenCalledTimes(1);
  expect(createEventSource).toHaveBeenCalledTimes(1);
});
