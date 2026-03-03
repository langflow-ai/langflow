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
