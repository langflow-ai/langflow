import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatSessionsDropdown } from "../chat-sessions-dropdown";

jest.mock(
  "@/components/core/playgroundComponent/hooks/use-get-flow-id",
  () => ({
    useGetFlowId: () => "flow-1",
  }),
);

jest.mock("../../hooks/use-session-labels", () => ({
  useSessionLabels: () =>
    new Map([["trigger:t1:e1", "Oct 29, 3:45:12 PM · Schedule"]]),
}));

describe("ChatSessionsDropdown", () => {
  it("names trigger runs by what started them and when", async () => {
    const user = userEvent.setup();
    render(
      <ChatSessionsDropdown
        sessions={["flow-1", "trigger:t1:e1", "my chat"]}
        sessionsPagination={{
          hasNextPage: false,
          isFetchingNextPage: false,
          fetchNextPage: jest.fn(),
        }}
      />,
    );

    await user.click(screen.getByTestId("session-selector-trigger"));

    expect(
      screen.getByRole("menuitem", { name: "Oct 29, 3:45:12 PM · Schedule" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: "my chat" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: "Default Session" }),
    ).toBeInTheDocument();
  });

  it("loads the next page from the menu and stays open", async () => {
    const user = userEvent.setup();
    const fetchNextPage = jest.fn().mockResolvedValue({ hasNextPage: true });
    render(
      <ChatSessionsDropdown
        sessions={["flow-1", "session-a"]}
        sessionsPagination={{
          hasNextPage: true,
          isFetchingNextPage: false,
          fetchNextPage,
        }}
      />,
    );

    await user.click(screen.getByTestId("session-selector-trigger"));
    await user.click(
      screen.getByRole("menuitem", { name: "Show more sessions" }),
    );

    expect(fetchNextPage).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("menuitem", { name: "session-a" }),
    ).toBeInTheDocument();
  });

  it("moves focus to the first loaded session when the last page loads", async () => {
    const user = userEvent.setup();
    const fetchNextPage = jest.fn().mockResolvedValue({ hasNextPage: false });
    const pagination = (hasNextPage: boolean) => ({
      hasNextPage,
      isFetchingNextPage: false,
      fetchNextPage,
    });
    const { rerender } = render(
      <ChatSessionsDropdown
        sessions={["flow-1", "session-a"]}
        sessionsPagination={pagination(true)}
      />,
    );
    await user.click(screen.getByTestId("session-selector-trigger"));
    screen.getByRole("menuitem", { name: "Show more sessions" }).focus();

    await user.keyboard("{Enter}");
    rerender(
      <ChatSessionsDropdown
        sessions={["flow-1", "session-a", "session-b"]}
        sessionsPagination={pagination(false)}
      />,
    );

    expect(screen.getByRole("menuitem", { name: "session-b" })).toHaveFocus();
  });
});
