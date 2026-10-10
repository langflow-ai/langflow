import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatSessionsDropdown } from "../chat-sessions-dropdown";

jest.mock(
  "@/components/core/playgroundComponent/hooks/use-get-flow-id",
  () => ({
    useGetFlowId: () => "flow-1",
  }),
);

describe("ChatSessionsDropdown", () => {
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
