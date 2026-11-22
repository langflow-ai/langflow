import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TriggerEventList from "../eventsDrawer/TriggerEventList";
import TriggerNodeBadge from "../TriggerNodeBadge";
import TriggerStateBadge from "../TriggerStateBadge";
import { makeEvent, makeTrigger } from "./fixtures";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <svg data-testid={`icon-${name}`} className={className} />
  ),
}));
jest.mock("../hooks/use-trigger-action-runner", () => ({
  useTriggerActionRunner: () => ({
    run: jest.fn(),
    busyId: null,
    dialogs: null,
  }),
}));
jest.mock("../eventsDrawer", () => ({ __esModule: true, default: () => null }));
jest.mock("@/controllers/API/queries/triggers", () => ({
  useTriggerPollingInterval: () => 5000,
}));

it.each(["node", "table"])(
  "shows a disabled trigger as ready to resume in the %s",
  (surface) => {
    const trigger = makeTrigger({
      provider: "whatsapp",
      state: "pending",
      reason: "ready_to_resume",
    });
    render(
      surface === "node" ? (
        <TriggerNodeBadge trigger={trigger} />
      ) : (
        <TriggerStateBadge state={trigger.state} reason={trigger.reason} />
      ),
    );

    expect(screen.getByText("Ready to resume")).toBeInTheDocument();
    expect(screen.queryByTestId("icon-LoaderCircle")).not.toBeInTheDocument();
  },
);

it.each([
  ["message", undefined, "Message received"],
  ["status", "sent", "Status sent"],
  ["status", "delivered", "Status delivered"],
  ["status", "read", "Status read"],
  ["status", "failed", "Delivery failed"],
  ["status", "__proto__", "Message status"],
  ["status", "toString", "Message status"],
])("names a WhatsApp %s %s event", (event, status, label) => {
  render(
    <TriggerEventList
      events={[
        makeEvent({
          payload: { provider: "whatsapp", data: { event, status } },
        }),
      ]}
      selectedId={null}
      onSelect={jest.fn()}
      maxAttempts={3}
    />,
  );

  expect(screen.getByTestId("trigger-event-evt-1")).toHaveTextContent(label!);
});

it.each([null, "not an object", { event: "unknown" }])(
  "keeps malformed WhatsApp event data readable",
  (data) => {
    render(
      <TriggerEventList
        events={[makeEvent({ payload: { provider: "whatsapp", data } })]}
        selectedId={null}
        onSelect={jest.fn()}
        maxAttempts={3}
      />,
    );

    expect(screen.getByTestId("trigger-event-evt-1")).toHaveTextContent(
      "Event",
    );
  },
);

it("stops showing pending setup when the server records a refused Resume", async () => {
  const trigger = makeTrigger({
    provider: "whatsapp",
    state: "pending",
    reason: "ready_to_resume",
    allowed_actions: ["resume"],
  });
  const { rerender } = render(<TriggerNodeBadge trigger={trigger} />);

  rerender(
    <TriggerNodeBadge
      trigger={{
        ...trigger,
        state: "error",
        reason: "error",
        last_error:
          "This app/WABA already has a receiver. One WhatsApp trigger may own it.",
      }}
    />,
  );
  expect(screen.getByText("Error")).toBeInTheDocument();
  expect(screen.queryByTestId("icon-LoaderCircle")).not.toBeInTheDocument();
  await userEvent.click(screen.getByTestId("trigger-node-badge"));
  expect(screen.getByTestId("trigger-last-error")).toHaveTextContent(
    "This app/WABA already has a receiver. One WhatsApp trigger may own it.",
  );
});
