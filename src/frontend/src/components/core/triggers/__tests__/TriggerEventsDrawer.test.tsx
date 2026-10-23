import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TriggerEventRead } from "@/controllers/API/queries/triggers";
import { axe } from "@/utils/a11y-test";
import TriggerEventsDrawer from "../eventsDrawer";
import { makeEvent, makeTrigger } from "./fixtures";

let mockEvents: TriggerEventRead[] = [];
const mockReplay = jest.fn();
const mockNavigate = jest.fn();
const mockFetchNextPage = jest.fn();

jest.mock("@/pages/FlowPage/components/TraceComponent/TraceDetailView", () => ({
  TraceDetailView: ({ traceId }: { traceId: string }) => (
    <div data-testid="opened-trace">{traceId}</div>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/controllers/API/queries/triggers", () => ({
  TRIGGER_EVENTS_PAGE_SIZE: 2,
  useTriggerEventsQuery: () => ({
    data: mockEvents.slice(0, 2),
    isLoading: false,
    isFetching: false,
    hasNextPage: true,
    isFetchingNextPage: false,
    fetchNextPage: mockFetchNextPage,
  }),
  useTriggerQuery: () => ({ data: undefined }),
  useReplayTriggerEventMutation: () => ({
    mutateAsync: mockReplay,
    isPending: false,
  }),
}));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: jest.fn(), setSuccessData: jest.fn() }),
}));

const failed = makeEvent({
  id: "failed",
  state: "failed",
  attempt: 3,
  error: "job_failed",
  payload: { text: "Checkout page returns 500" },
});
const test = makeEvent({ id: "test", dedupe_key: "test:1", payload: {} });

describe("TriggerEventsDrawer", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockEvents = [failed, test];
  });

  const open = () =>
    render(
      <TriggerEventsDrawer trigger={makeTrigger()} onOpenChange={jest.fn()} />,
    );

  it("shows the newest event's normalized payload and mapped error", () => {
    open();
    const detail = screen.getByTestId("trigger-event-detail");

    expect(
      within(detail).getByTestId("trigger-event-payload"),
    ).toHaveTextContent("Checkout page returns 500");
    expect(
      within(detail).getByText("The run didn't complete."),
    ).toBeInTheDocument();
    expect(within(detail).getByText("3 of 3")).toBeInTheDocument();
  });

  it("filters to tests and names an event without text by its origin", async () => {
    open();
    await userEvent.click(screen.getByTestId("trigger-event-failed"));
    await userEvent.click(screen.getByTestId("trigger-events-filter-tests"));

    expect(screen.queryByTestId("trigger-event-failed")).toBeNull();
    expect(screen.getByTestId("trigger-event-test")).toHaveTextContent(
      "Test event",
    );
    expect(screen.getByTestId("trigger-events-filter-tests")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("trigger-event-payload")).toHaveTextContent("{}");
  });

  it("confirms a replay, posts it, and does not imply the original re-ran", async () => {
    mockReplay.mockResolvedValue(
      makeEvent({ id: "new", replay_of_event_id: "failed" }),
    );
    open();

    await userEvent.click(screen.getByTestId("trigger-event-replay"));
    expect(screen.getByTestId("trigger-replay-dialog")).toHaveTextContent(
      "The original event keeps its result.",
    );
    await userEvent.click(screen.getByTestId("trigger-replay-confirm"));

    expect(mockReplay).toHaveBeenCalledWith({
      triggerId: "trg-1",
      eventId: "failed",
    });
  });

  it("keeps replay visible but inert when the server blocks it", async () => {
    render(
      <TriggerEventsDrawer
        trigger={makeTrigger({
          allowed_actions: [],
          blocked_actions: { replay: "paused" },
        })}
        onOpenChange={jest.fn()}
      />,
    );
    const replay = screen.getByTestId("trigger-event-replay");

    expect(replay).toHaveAttribute("aria-disabled", "true");
    expect(replay).toHaveAccessibleDescription("Resume the trigger first.");
    await userEvent.click(replay);
    expect(screen.queryByTestId("trigger-replay-dialog")).toBeNull();
  });

  it("shows lineage from a replay back to its original", async () => {
    mockEvents = [makeEvent({ id: "r", replay_of_event_id: "failed" }), failed];
    open();

    expect(screen.getByTestId("trigger-event-lineage")).toHaveTextContent(
      "Replay of",
    );
  });

  it("offers older events only when the server returned an extra row", () => {
    mockEvents = [failed, test, makeEvent({ id: "third" })];
    open();

    expect(screen.queryByTestId("trigger-event-third")).toBeNull();
    expect(screen.getByTestId("trigger-events-load-more")).toBeInTheDocument();
  });

  it("can load older failures when the current page has no matches", async () => {
    mockEvents = [test];
    open();
    await userEvent.click(screen.getByTestId("trigger-events-filter-failed"));
    await userEvent.click(screen.getByTestId("trigger-events-load-more"));
    expect(mockFetchNextPage).toHaveBeenCalled();
  });

  it("opens the selected event's trace", async () => {
    open();
    await userEvent.click(screen.getByTestId("trigger-event-open-run"));
    expect(await screen.findByTestId("opened-trace")).toHaveTextContent(
      "job-1",
    );
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
