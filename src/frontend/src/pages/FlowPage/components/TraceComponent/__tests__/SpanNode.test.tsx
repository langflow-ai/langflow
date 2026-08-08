import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode } from "react";
import { SpanNode } from "../SpanNode";
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
  Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

describe("SpanNode", () => {
  it("aria-label contains the full visible span name (including any UUID suffix)", () => {
    const uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
    const name = `New flow - ${uuid}`;
    render(
      <SpanNode
        span={buildSpan({ name })}
        depth={0}
        isExpanded={false}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    const node = screen.getByTestId("span-node-span-1");
    expect(node).toHaveAttribute("aria-label", expect.stringContaining(name));
    expect(screen.getByText(name)).toBeInTheDocument();
  });

  it("renders name, tokens, latency, and status", () => {
    render(
      <SpanNode
        span={buildSpan({
          tokenUsage: {
            promptTokens: 10,
            completionTokens: 20,
            totalTokens: 1200,
            cost: 0.5,
          },
        })}
        depth={0}
        isExpanded={true}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    const node = screen.getByTestId("span-node-span-1");
    expect(node).toHaveAttribute("role", "treeitem");
    expect(node).toHaveAttribute("aria-selected", "false");
    expect(node).not.toHaveAttribute("aria-expanded");

    expect(screen.getByText("Test Span")).toBeInTheDocument();
    expect(screen.getByText("1.2k")).toBeInTheDocument();
    expect(screen.getByText("1.20 s")).toBeInTheDocument();

    const statusIcon = screen.getByTestId("flow-log-status-ok");
    expect(statusIcon).toHaveAttribute("aria-label", "ok");
  });

  it("does not render token count when tokenUsage is absent", () => {
    render(
      <SpanNode
        span={buildSpan({ tokenUsage: undefined })}
        depth={0}
        isExpanded={false}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.queryByTestId("icon-Coins")).not.toBeInTheDocument();
  });

  it("applies selected styles and aria-selected when isSelected is true", () => {
    render(
      <SpanNode
        span={buildSpan({
          tokenUsage: {
            promptTokens: 1,
            completionTokens: 1,
            totalTokens: 10,
            cost: 0,
          },
        })}
        depth={0}
        isExpanded={false}
        isSelected={true}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    const node = screen.getByTestId("span-node-span-1");
    expect(node).toHaveAttribute("aria-selected", "true");
    expect(node).toHaveClass("bg-muted");

    const spans = node.querySelectorAll("span");
    const contrastedSpans = Array.from(spans).filter((s) =>
      s.className.includes("text-foreground/65"),
    );
    expect(contrastedSpans.length).toBeGreaterThanOrEqual(2);
  });

  it("calls onSelect when the row is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();

    render(
      <SpanNode
        span={buildSpan()}
        depth={0}
        isExpanded={true}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={onSelect}
      />,
    );

    await user.click(screen.getByTestId("span-node-span-1"));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("calls onSelect when Enter is pressed on the row", async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();

    render(
      <SpanNode
        span={buildSpan()}
        depth={0}
        isExpanded={false}
        isSelected={false}
        tabIndex={0}
        onToggle={jest.fn()}
        onSelect={onSelect}
      />,
    );

    const node = screen.getByTestId("span-node-span-1");
    node.focus();
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("passes tabIndex and aria-posinset/setsize to the treeitem", () => {
    render(
      <SpanNode
        span={buildSpan()}
        depth={0}
        isExpanded={false}
        isSelected={false}
        tabIndex={0}
        posInSet={2}
        setSize={5}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    const node = screen.getByTestId("span-node-span-1");
    expect(node).toHaveAttribute("tabindex", "0");
    expect(node).toHaveAttribute("aria-posinset", "2");
    expect(node).toHaveAttribute("aria-setsize", "5");
  });

  it("sets aria-expanded based on isExpanded when span has children", () => {
    const withChild = buildSpan({ children: [buildSpan({ id: "child-1" })] });

    const { rerender } = render(
      <SpanNode
        span={withChild}
        depth={0}
        isExpanded={false}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.getByTestId("span-node-span-1")).toHaveAttribute(
      "aria-expanded",
      "false",
    );

    rerender(
      <SpanNode
        span={withChild}
        depth={0}
        isExpanded={true}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.getByTestId("span-node-span-1")).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("sets expand button aria-label based on expanded state", () => {
    const withChild = buildSpan({ children: [buildSpan({ id: "child-1" })] });

    const { rerender } = render(
      <SpanNode
        span={withChild}
        depth={0}
        isExpanded={false}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.getByRole("button")).toHaveAttribute(
      "aria-label",
      "Expand span",
    );

    rerender(
      <SpanNode
        span={withChild}
        depth={0}
        isExpanded={true}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.getByRole("button")).toHaveAttribute(
      "aria-label",
      "Collapse span",
    );
  });

  it("applies paddingLeft based on depth", () => {
    const { rerender } = render(
      <SpanNode
        span={buildSpan()}
        depth={0}
        isExpanded={false}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.getByTestId("span-node-span-1")).toHaveStyle(
      "padding-left: 0.5rem",
    );

    rerender(
      <SpanNode
        span={buildSpan()}
        depth={2}
        isExpanded={false}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.getByTestId("span-node-span-1")).toHaveStyle(
      "padding-left: 2.5rem",
    );
  });

  it("renders error status icon and applies error class to span name", () => {
    render(
      <SpanNode
        span={buildSpan({ status: "error" })}
        depth={0}
        isExpanded={false}
        isSelected={false}
        onToggle={jest.fn()}
        onSelect={jest.fn()}
      />,
    );

    const statusIcon = screen.getByTestId("flow-log-status-error");
    expect(statusIcon).toHaveAttribute("aria-label", "error");

    const nameEl = screen.getByText("Test Span");
    expect(nameEl).toHaveClass("text-error-foreground");
  });

  it("calls onToggle (and not onSelect) when expand button is clicked", async () => {
    const user = userEvent.setup();
    const onToggle = jest.fn();
    const onSelect = jest.fn();

    render(
      <SpanNode
        span={buildSpan({ children: [buildSpan({ id: "child-1" })] })}
        depth={0}
        isExpanded={false}
        isSelected={false}
        onToggle={onToggle}
        onSelect={onSelect}
      />,
    );

    const node = screen.getByTestId("span-node-span-1");
    const button = within(node).getByRole("button");

    await user.click(button);
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("does not toggle when span has no children", async () => {
    const user = userEvent.setup();
    const onToggle = jest.fn();

    render(
      <SpanNode
        span={buildSpan({ children: [] })}
        depth={0}
        isExpanded={false}
        isSelected={false}
        onToggle={onToggle}
        onSelect={jest.fn()}
      />,
    );

    const node = screen.getByTestId("span-node-span-1");
    const button = within(node).getByRole("button", { hidden: true });
    expect(button).toHaveAttribute("aria-hidden", "true");

    await user.click(button);
    expect(onToggle).not.toHaveBeenCalled();
  });
});
