import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarOpenView } from "../sidebar-open-view";

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (s: { setNewChatOnPlayground: jest.Mock }) => unknown) =>
    selector({ setNewChatOnPlayground: jest.fn() }),
}));

jest.mock("@/stores/voiceStore", () => ({
  useVoiceStore: (
    selector: (s: { setNewSessionCloseVoiceAssistant: jest.Mock }) => unknown,
  ) => selector({ setNewSessionCloseVoiceAssistant: jest.fn() }),
}));

jest.mock("../IOFieldView/components/session-selector", () => ({
  __esModule: true,
  default: ({ session }: { session: string }) => (
    <div data-testid="session-selector">{session}</div>
  ),
}));

describe("SidebarOpenView", () => {
  it("loads the next page of older sessions from the show more button", () => {
    const fetchNextPage = jest.fn().mockResolvedValue({ hasNextPage: true });
    render(
      <TooltipProvider>
        <SidebarOpenView
          sessions={["flow", "session-a"]}
          sessionsPagination={{
            hasNextPage: true,
            isFetchingNextPage: false,
            fetchNextPage,
          }}
          setSelectedViewField={jest.fn()}
          setvisibleSession={jest.fn()}
          handleDeleteSession={jest.fn()}
          visibleSession="flow"
          selectedViewField={undefined}
          playgroundPage
          setActiveSession={jest.fn()}
        />
      </TooltipProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Show more sessions" }));

    expect(fetchNextPage).toHaveBeenCalledTimes(1);
  });
});
