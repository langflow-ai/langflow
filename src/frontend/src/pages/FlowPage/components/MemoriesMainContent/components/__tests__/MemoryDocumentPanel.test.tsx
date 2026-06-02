import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryDocumentPanel } from "../MemoryDocumentPanel";

jest.mock("@/components/ui/dialog", () => ({
  __esModule: true,
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  Dialog: ({ children, onOpenChange }: any) => (
    <div>
      <button
        data-testid="dialog-close-trigger"
        onClick={() => onOpenChange?.(false)}
      >
        close
      </button>
      {children}
    </div>
  ),
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  DialogContent: ({ children }: any) => <div>{children}</div>,
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  DialogTitle: ({ children, ...props }: any) => (
    <div {...props}>{children}</div>
  ),
}));

describe("MemoryDocumentPanel", () => {
  it("renders empty state when no document is selected", () => {
    render(
      <MemoryDocumentPanel
        open
        onOpenChange={jest.fn()}
        selectedDocument={null}
      />,
    );

    expect(screen.getByText("No chunk selected.")).toBeInTheDocument();
  });

  it("renders selected document details", () => {
    render(
      <MemoryDocumentPanel
        open
        onOpenChange={jest.fn()}
        selectedDocument={
          {
            message_id: "msg-1",
            session_id: "session-1",
            sender: "user",
            timestamp: "2025-01-01T10:00:00.000Z",
            content: "hello world",
            // biome-ignore lint/suspicious/noExplicitAny: legacy
          } as any
        }
      />,
    );

    expect(screen.getByText("Chunk Details")).toBeInTheDocument();
    expect(screen.getByText("msg-1")).toBeInTheDocument();
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("calls onOpenChange(false) when the dialog requests close", () => {
    const onOpenChange = jest.fn();
    render(
      <MemoryDocumentPanel
        open
        onOpenChange={onOpenChange}
        selectedDocument={null}
      />,
    );

    fireEvent.click(screen.getByTestId("dialog-close-trigger"));

    expect(onOpenChange).toHaveBeenCalledTimes(1);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("renders dash for timestamp when document has no timestamp field", () => {
    render(
      <MemoryDocumentPanel
        open
        onOpenChange={jest.fn()}
        selectedDocument={
          {
            message_id: "msg-3",
            session_id: "s1",
            content: "data without timestamps",
            // biome-ignore lint/suspicious/noExplicitAny: legacy
          } as any
        }
      />,
    );

    // formatTimestamp(undefined) → "-"
    const timestampLabel = screen.getByText("Timestamp:");
    expect(timestampLabel.parentElement?.textContent).toContain("-");
  });
});
