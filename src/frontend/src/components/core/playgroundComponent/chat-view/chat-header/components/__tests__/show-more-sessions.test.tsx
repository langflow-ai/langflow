import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ShowMoreSessions } from "../show-more-sessions";

const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: { setErrorData: jest.Mock }) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
}));

// A session list the way the surfaces render it: one wrapper per row with a
// focusable row button, and the control as the last child.
function SessionList({
  rows,
  hasNextPage,
  fetchNextPage,
}: {
  rows: string[];
  hasNextPage: boolean;
  fetchNextPage: jest.Mock;
}) {
  return (
    <div>
      {rows.map((row) => (
        <div key={row}>
          <div role="button" tabIndex={0}>
            {row}
          </div>
        </div>
      ))}
      <ShowMoreSessions
        pagination={{ hasNextPage, isFetchingNextPage: false, fetchNextPage }}
      />
    </div>
  );
}

const showMore = () =>
  screen.getByRole("button", { name: "Show more sessions" });

beforeEach(() => mockSetErrorData.mockReset());

describe("ShowMoreSessions", () => {
  it("moves focus to the first loaded session when the last page loads", async () => {
    const user = userEvent.setup();
    const fetchNextPage = jest.fn().mockResolvedValue({ hasNextPage: false });
    const { rerender } = render(
      <SessionList rows={["a"]} hasNextPage fetchNextPage={fetchNextPage} />,
    );

    await user.click(showMore());
    // The query reports the last page before the synced rows render.
    rerender(
      <SessionList
        rows={["a"]}
        hasNextPage={false}
        fetchNextPage={fetchNextPage}
      />,
    );
    rerender(
      <SessionList
        rows={["a", "b", "c"]}
        hasNextPage={false}
        fetchNextPage={fetchNextPage}
      />,
    );

    expect(screen.getByRole("button", { name: "b" })).toHaveFocus();
  });

  it("does not take focus back from where the user went while the page loaded", async () => {
    const user = userEvent.setup();
    const fetchNextPage = jest.fn().mockResolvedValue({ hasNextPage: false });
    const { rerender } = render(
      <>
        <SessionList rows={["a"]} hasNextPage fetchNextPage={fetchNextPage} />
        <textarea aria-label="chat input" />
      </>,
    );

    await user.click(showMore());
    await user.click(screen.getByRole("textbox", { name: "chat input" }));
    rerender(
      <>
        <SessionList
          rows={["a", "b"]}
          hasNextPage={false}
          fetchNextPage={fetchNextPage}
        />
        <textarea aria-label="chat input" />
      </>,
    );

    expect(screen.getByRole("textbox", { name: "chat input" })).toHaveFocus();
  });

  it("stops waiting for loaded rows after one extra render", async () => {
    const user = userEvent.setup();
    const fetchNextPage = jest.fn().mockResolvedValue({ hasNextPage: false });
    const { rerender } = render(
      <SessionList rows={["a"]} hasNextPage fetchNextPage={fetchNextPage} />,
    );
    await user.click(showMore());
    const lastPageWithoutNewRows = () => (
      <SessionList
        rows={["a"]}
        hasNextPage={false}
        fetchNextPage={fetchNextPage}
      />
    );
    rerender(lastPageWithoutNewRows());
    rerender(lastPageWithoutNewRows());

    // A row added much later (e.g. a new chat) must not pull focus.
    rerender(
      <SessionList
        rows={["a", "b"]}
        hasNextPage={false}
        fetchNextPage={fetchNextPage}
      />,
    );

    expect(screen.getByRole("button", { name: "b" })).not.toHaveFocus();
  });

  it("keeps focus on the control while older pages remain", async () => {
    const user = userEvent.setup();
    const fetchNextPage = jest.fn().mockResolvedValue({ hasNextPage: true });
    const { rerender } = render(
      <SessionList rows={["a"]} hasNextPage fetchNextPage={fetchNextPage} />,
    );

    await user.click(showMore());
    rerender(
      <SessionList
        rows={["a", "b"]}
        hasNextPage
        fetchNextPage={fetchNextPage}
      />,
    );

    expect(showMore()).toHaveFocus();
  });

  it("reports a failed page and stays available to retry", async () => {
    const user = userEvent.setup();
    const fetchNextPage = jest
      .fn()
      .mockResolvedValue({ hasNextPage: true, isFetchNextPageError: true });
    render(
      <SessionList rows={["a"]} hasNextPage fetchNextPage={fetchNextPage} />,
    );

    await user.click(showMore());

    await waitFor(() =>
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "Error loading more sessions.",
      }),
    );
    expect(showMore()).toBeEnabled();
  });
});
