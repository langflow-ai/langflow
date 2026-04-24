import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SpanTree } from "../SpanTree";
import { buildSpan } from "./spanTestUtils";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({
    name,
    dataTestId,
    skipFallback,
    ...props
  }: {
    name: string;
    dataTestId?: string;
    skipFallback?: boolean;
  }) => (
    <span
      data-testid={dataTestId ?? `icon-${name}`}
      data-icon-name={name}
      {...props}
    />
  ),
}));

jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}));

const rootDefaults = {
  id: "root-1",
  name: "Root Span",
  type: "chain" as const,
};

describe("SpanTree", () => {
  it("renders a tree and expands root spans by default", () => {
    const child = buildSpan({ id: "child-1", name: "Child Span" });
    const root = buildSpan({ ...rootDefaults, children: [child] });

    render(
      <SpanTree
        spans={[root]}
        selectedSpanId={null}
        onSelectSpan={jest.fn()}
      />,
    );

    expect(screen.getByTestId("span-tree")).toHaveAttribute("role", "tree");
    expect(screen.getByTestId("span-node-root-1")).toBeInTheDocument();
    expect(screen.getByTestId("span-node-child-1")).toBeInTheDocument();
    expect(screen.getByText("Root Span")).toBeInTheDocument();
    expect(screen.getByText("Child Span")).toBeInTheDocument();
  });

  it("collapses and expands children when toggled", async () => {
    const user = userEvent.setup();
    const child = buildSpan({ id: "child-1", name: "Child Span" });
    const root = buildSpan({ ...rootDefaults, children: [child] });

    render(
      <SpanTree
        spans={[root]}
        selectedSpanId={null}
        onSelectSpan={jest.fn()}
      />,
    );

    expect(screen.getByTestId("span-node-child-1")).toBeInTheDocument();

    const rootNode = screen.getByTestId("span-node-root-1");
    await user.click(within(rootNode).getByRole("button"));
    expect(screen.queryByTestId("span-node-child-1")).not.toBeInTheDocument();

    await user.click(within(rootNode).getByRole("button"));
    expect(screen.getByTestId("span-node-child-1")).toBeInTheDocument();
  });

  it("calls onSelectSpan with the clicked span", async () => {
    const user = userEvent.setup();
    const onSelectSpan = jest.fn();
    const child = buildSpan({ id: "child-1", name: "Child Span" });
    const root = buildSpan({ ...rootDefaults, children: [child] });

    render(
      <SpanTree
        spans={[root]}
        selectedSpanId={null}
        onSelectSpan={onSelectSpan}
      />,
    );

    await user.click(screen.getByTestId("span-node-child-1"));
    expect(onSelectSpan).toHaveBeenCalledTimes(1);
    expect(onSelectSpan).toHaveBeenCalledWith(child);
  });

  it("marks the selected span via aria-selected", () => {
    const child = buildSpan({ id: "child-1", name: "Child Span" });
    const root = buildSpan({ ...rootDefaults, children: [child] });

    render(
      <SpanTree
        spans={[root]}
        selectedSpanId={child.id}
        onSelectSpan={jest.fn()}
      />,
    );

    expect(screen.getByTestId("span-node-child-1")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("span-node-root-1")).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });
});
