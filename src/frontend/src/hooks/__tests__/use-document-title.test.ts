import { renderHook } from "@testing-library/react";
import { formatDocumentTitle, useDocumentTitle } from "../use-document-title";

describe("formatDocumentTitle", () => {
  it("brands the page title", () => {
    expect(formatDocumentTitle("Flows")).toBe("Flows | Langflow");
  });

  it("does not double-brand a title that already names the product", () => {
    expect(formatDocumentTitle("Langflow API Keys")).toBe("Langflow API Keys");
  });

  it("falls back to the product name for an empty title", () => {
    expect(formatDocumentTitle(undefined)).toBe("Langflow");
    expect(formatDocumentTitle(null)).toBe("Langflow");
    expect(formatDocumentTitle("   ")).toBe("Langflow");
  });
});

describe("useDocumentTitle", () => {
  it("sets the document title while mounted and resets it on unmount", () => {
    const { unmount } = renderHook(() => useDocumentTitle("Global Variables"));
    expect(document.title).toBe("Global Variables | Langflow");

    unmount();
    expect(document.title).toBe("Langflow");
  });

  it("follows a title that resolves after the first render", () => {
    const { rerender } = renderHook(
      ({ title }: { title?: string }) => useDocumentTitle(title),
      { initialProps: { title: undefined } },
    );
    expect(document.title).toBe("Langflow");

    rerender({ title: "My Flow" });
    expect(document.title).toBe("My Flow | Langflow");
  });
});
