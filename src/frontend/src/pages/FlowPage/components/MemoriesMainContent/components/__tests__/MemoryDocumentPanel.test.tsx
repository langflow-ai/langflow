import { render, screen } from "@testing-library/react";
import { MemoryDocumentPanel } from "../MemoryDocumentPanel";

jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children }: any) => <div>{children}</div>,
  DialogContent: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <div>{children}</div>,
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
          } as any
        }
      />,
    );

    expect(screen.getByText("Chunk Details")).toBeInTheDocument();
    expect(screen.getByText("msg-1")).toBeInTheDocument();
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });
});
