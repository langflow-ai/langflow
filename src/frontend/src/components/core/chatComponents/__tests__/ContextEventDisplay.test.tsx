import { render, screen } from "@testing-library/react";
import type { ContextEvent } from "@/types/chat";
import { ContextEventDisplay } from "../ContextEventDisplay";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

const show = (event: Omit<ContextEvent, "id">) =>
  render(<ContextEventDisplay event={{ id: "e1", ...event }} />);

describe("ContextEventDisplay", () => {
  it("shows a running fold with the number of messages while it streams", () => {
    show({ kind: "fold", state: "running", messages: 18 });
    const label = screen.getByText("Summarizing 18 older messages…");
    expect(label).toHaveClass("animate-pulse");
    expect(screen.getByTestId("icon-History")).toBeInTheDocument();
  });

  it("shows a finished fold with its duration", () => {
    show({ kind: "fold", state: "done", messages: 1, duration: 2500 });
    expect(screen.getByTestId("context-event-fold-done")).toHaveTextContent(
      "Summarized 1 older message· 2.5s",
    );
  });

  it("says a failed fold retries on the next turn", () => {
    show({ kind: "fold", state: "failed", messages: 4, duration: 900 });
    expect(screen.getByTestId("context-event-fold-failed")).toHaveTextContent(
      "Could not summarize older messages. The next turn tries again.",
    );
  });

  it("shows a compaction with the tokens before and after", () => {
    show({
      kind: "compaction",
      state: "done",
      tokens_before: 104000,
      tokens_after: 33500,
      duration: 4100,
    });
    expect(
      screen.getByTestId("context-event-compaction-done"),
    ).toHaveTextContent(
      "Compacted the context of this run from 104,000 to 33,500 tokens",
    );
  });
});
