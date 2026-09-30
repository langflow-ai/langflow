import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PaginatorComponent from "../index";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

// Radix Select needs a portal target
beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: jest.fn().mockReturnValue({
      matches: false,
      addListener: jest.fn(),
      removeListener: jest.fn(),
    }),
  });
});

const noop = jest.fn();

function renderPaginator(
  overrides: Partial<Parameters<typeof PaginatorComponent>[0]> = {},
) {
  return render(
    <PaginatorComponent
      pageSize={20}
      pageIndex={1}
      totalRowsCount={0}
      paginate={noop}
      {...overrides}
    />,
  );
}

// ---------------------------------------------------------------------------
// Empty state (the bug: "-19-0 of 0 items")
// ---------------------------------------------------------------------------

describe("empty state", () => {
  it("shows '0 items' when totalRowsCount is 0", () => {
    renderPaginator({ totalRowsCount: 0, pageIndex: 1, pageSize: 20 });
    expect(screen.getByText(/^0 items$/)).toBeInTheDocument();
    expect(screen.queryByText(/of 0 items/)).not.toBeInTheDocument();
  });

  it("does not show a negative start when pageIndex is 0 and totalRowsCount is 0", () => {
    // pageIndex=0 would previously produce (0-1)*20+1 = -19
    renderPaginator({ totalRowsCount: 0, pageIndex: 0, pageSize: 20 });
    expect(screen.queryByText(/-19/)).not.toBeInTheDocument();
    expect(screen.getByText(/^0 items$/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Normal state
// ---------------------------------------------------------------------------

describe("normal state", () => {
  it("shows correct range for first page", () => {
    renderPaginator({
      totalRowsCount: 50,
      pageIndex: 1,
      pageSize: 20,
      pages: 3,
    });
    expect(screen.getByText(/^1-20$/)).toBeInTheDocument();
    expect(screen.getByText(/of 50/)).toBeInTheDocument();
  });

  it("shows correct range for middle page", () => {
    renderPaginator({
      totalRowsCount: 50,
      pageIndex: 2,
      pageSize: 20,
      pages: 3,
    });
    expect(screen.getByText(/^21-40$/)).toBeInTheDocument();
  });

  it("clamps end of range to totalRowsCount on last page", () => {
    renderPaginator({
      totalRowsCount: 45,
      pageIndex: 3,
      pageSize: 20,
      pages: 3,
    });
    // 3rd page: start=41, end=min(45, 60)=45
    expect(screen.getByText(/^41-45$/)).toBeInTheDocument();
  });

  it("shows 'items' label when isComponent is undefined", () => {
    renderPaginator({ totalRowsCount: 10, pageIndex: 1, pageSize: 20 });
    expect(screen.getByText(/items/)).toBeInTheDocument();
  });

  it("shows 'components' label when isComponent is true", () => {
    renderPaginator({
      totalRowsCount: 10,
      pageIndex: 1,
      pageSize: 20,
      isComponent: true,
    });
    expect(screen.getByText(/components/)).toBeInTheDocument();
  });

  it("shows 'flows' label when isComponent is false", () => {
    renderPaginator({
      totalRowsCount: 10,
      pageIndex: 1,
      pageSize: 20,
      isComponent: false,
    });
    expect(screen.getByText(/flows/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Navigation buttons
// ---------------------------------------------------------------------------

describe("navigation buttons", () => {
  it("disables previous button on first page", () => {
    renderPaginator({
      totalRowsCount: 50,
      pageIndex: 1,
      pageSize: 20,
      pages: 3,
    });
    const prev = screen.getByRole("button", { name: /previous/i });
    expect(prev).toBeDisabled();
  });

  it("enables previous button when not on first page", () => {
    renderPaginator({
      totalRowsCount: 50,
      pageIndex: 2,
      pageSize: 20,
      pages: 3,
    });
    const prev = screen.getByRole("button", { name: /previous/i });
    expect(prev).not.toBeDisabled();
  });

  it("calls paginate with decremented index when previous is clicked", async () => {
    const user = userEvent.setup();
    const paginate = jest.fn();
    renderPaginator({
      totalRowsCount: 50,
      pageIndex: 2,
      pageSize: 20,
      pages: 3,
      paginate,
    });
    await user.click(screen.getByRole("button", { name: /previous/i }));
    expect(paginate).toHaveBeenCalledWith(1, 20);
  });

  it("calls paginate with incremented index when next is clicked", async () => {
    const user = userEvent.setup();
    const paginate = jest.fn();
    renderPaginator({
      totalRowsCount: 50,
      pageIndex: 1,
      pageSize: 20,
      pages: 3,
      paginate,
    });
    await user.click(screen.getByRole("button", { name: /next/i }));
    expect(paginate).toHaveBeenCalledWith(2, 20);
  });
});
