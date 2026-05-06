import { fireEvent, render, screen } from "@testing-library/react";
import PaginatorComponent from "../index";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("../../../ui/select", () => {
  const React = require("react");
  return {
    Select: ({
      children,
      value,
      onValueChange,
    }: {
      children: React.ReactNode;
      value: string;
      onValueChange: (value: string) => void;
    }) => (
      <select
        data-testid="page-select"
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
      >
        {children}
      </select>
    ),
    SelectContent: ({ children }: { children: React.ReactNode }) => (
      <>{children}</>
    ),
    SelectItem: ({
      children,
      value,
    }: {
      children: React.ReactNode;
      value: string;
    }) => <option value={value}>{children}</option>,
    SelectTrigger: ({ children }: { children: React.ReactNode }) => (
      <>{children}</>
    ),
    SelectValue: () => null,
  };
});

const renderPaginator = (
  overrides: Partial<React.ComponentProps<typeof PaginatorComponent>> = {},
) => {
  const paginate = jest.fn();
  const utils = render(
    <PaginatorComponent
      pageSize={20}
      pageIndex={1}
      totalRowsCount={0}
      paginate={paginate}
      {...overrides}
    />,
  );
  return { paginate, ...utils };
};

describe("PaginatorComponent", () => {
  describe("empty state", () => {
    it("renders '0 items' instead of '1-0 of 0 items' when there are no rows", () => {
      renderPaginator({ totalRowsCount: 0 });

      expect(screen.getByText("0 items")).toBeInTheDocument();
      expect(screen.queryByText(/1-0/)).not.toBeInTheDocument();
      expect(screen.queryByText(/of 0 items/)).not.toBeInTheDocument();
    });

    it("uses 'flows' label when isComponent is false", () => {
      renderPaginator({ totalRowsCount: 0, isComponent: false });
      expect(screen.getByText("0 flows")).toBeInTheDocument();
    });

    it("uses 'components' label when isComponent is true", () => {
      renderPaginator({ totalRowsCount: 0, isComponent: true });
      expect(screen.getByText("0 components")).toBeInTheDocument();
    });

    it("renders 'of 1 pages' instead of 'of 0 pages' when empty", () => {
      renderPaginator({ totalRowsCount: 0 });
      expect(screen.getByText("of 1 pages")).toBeInTheDocument();
    });

    it("disables both prev and next when there are no rows", () => {
      renderPaginator({ totalRowsCount: 0 });
      const prev = screen.getByRole("button", { name: /previous page/i });
      const next = screen.getByRole("button", { name: /next page/i });
      expect(prev).toBeDisabled();
      expect(next).toBeDisabled();
    });
  });

  describe("populated state", () => {
    it("renders the correct range on the first page", () => {
      renderPaginator({ totalRowsCount: 45, pageSize: 20, pageIndex: 1 });
      expect(screen.getByText(/1-20/)).toBeInTheDocument();
      expect(screen.getByText(/of 45 items/)).toBeInTheDocument();
    });

    it("clamps the range end to totalRowsCount on the last page", () => {
      renderPaginator({ totalRowsCount: 45, pageSize: 20, pageIndex: 3 });
      expect(screen.getByText(/41-45/)).toBeInTheDocument();
    });

    it("renders the correct page count", () => {
      renderPaginator({ totalRowsCount: 45, pageSize: 20, pageIndex: 1 });
      expect(screen.getByText("of 3 pages")).toBeInTheDocument();
    });

    it("respects an explicit pages prop", () => {
      renderPaginator({
        totalRowsCount: 45,
        pageSize: 20,
        pageIndex: 1,
        pages: 7,
      });
      expect(screen.getByText("of 7 pages")).toBeInTheDocument();
    });

    it("disables prev on the first page and next on the last page", () => {
      const { rerender, paginate } = renderPaginator({
        totalRowsCount: 45,
        pageSize: 20,
        pageIndex: 1,
      });
      expect(
        screen.getByRole("button", { name: /previous page/i }),
      ).toBeDisabled();
      expect(
        screen.getByRole("button", { name: /next page/i }),
      ).not.toBeDisabled();

      rerender(
        <PaginatorComponent
          pageSize={20}
          pageIndex={3}
          totalRowsCount={45}
          paginate={paginate}
        />,
      );
      expect(
        screen.getByRole("button", { name: /previous page/i }),
      ).not.toBeDisabled();
      expect(screen.getByRole("button", { name: /next page/i })).toBeDisabled();
    });

    it("calls paginate with the next page when next is clicked", () => {
      const { paginate } = renderPaginator({
        totalRowsCount: 45,
        pageSize: 20,
        pageIndex: 1,
      });
      fireEvent.click(screen.getByRole("button", { name: /next page/i }));
      expect(paginate).toHaveBeenCalledWith(2, 20);
    });

    it("calls paginate with the previous page when prev is clicked", () => {
      const { paginate } = renderPaginator({
        totalRowsCount: 45,
        pageSize: 20,
        pageIndex: 2,
      });
      fireEvent.click(screen.getByRole("button", { name: /previous page/i }));
      expect(paginate).toHaveBeenCalledWith(1, 20);
    });
  });
});
