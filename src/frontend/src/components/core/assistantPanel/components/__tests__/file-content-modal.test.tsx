/**
 * F3 — file content modal renders inline content via SanitizedMarkdown.
 *
 * Content arrives on the message itself (from the SSE ``file_written`` event)
 * — the modal does NOT fetch. We assert the wiring: it delegates rendering
 * to SanitizedMarkdown with the file's text, and shows a clear "preview not
 * available" fallback when content is missing (e.g., edit_file events).
 *
 * XSS-stripping is the responsibility of SanitizedMarkdown's
 * rehype-sanitize pipeline (covered by the schema tests in
 * ``utils/sanitizeSchema``), so we mock it here to a minimal stand-in.
 */

import "@testing-library/jest-dom";

jest.mock("@/components/core/sanitizedMarkdown", () => ({
  __esModule: true,
  SanitizedMarkdown: ({ chatMessage }: { chatMessage: string }) => (
    <div data-testid="sanitized-markdown">{chatMessage}</div>
  ),
}));

import { render, screen } from "@testing-library/react";

import { FileContentModal } from "../file-content-modal";

describe("FileContentModal — F3", () => {
  it("should delegate rendering to SanitizedMarkdown with the inline content", () => {
    render(
      <FileContentModal
        path="DOCS.md"
        content={"# Title\n\nHello **world**."}
        open
        onClose={jest.fn()}
      />,
    );

    expect(screen.getByTestId("sanitized-markdown")).toBeInTheDocument();
    expect(screen.getByTestId("sanitized-markdown")).toHaveTextContent(
      "# Title Hello **world**.",
    );
  });

  it("should render the preview-not-available notice when content is undefined", () => {
    render(
      <FileContentModal
        path="DOCS.md"
        content={undefined}
        open
        onClose={jest.fn()}
      />,
    );

    expect(screen.getByTestId("file-content-modal-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("sanitized-markdown")).not.toBeInTheDocument();
  });

  it("should pass agent-generated content through verbatim (sanitization is SanitizedMarkdown's job)", () => {
    render(
      <FileContentModal
        path="DOCS.md"
        content={"# Safe\n\n<script>x=1</script>"}
        open
        onClose={jest.fn()}
      />,
    );

    expect(screen.getByTestId("sanitized-markdown")).toBeInTheDocument();
    // No actual <script> tag injected — the mock renders the prop as text,
    // and the production renderer applies the sanitize schema.
    expect(document.querySelector("script")).toBeNull();
  });

  it("should not render when open is false", () => {
    render(
      <FileContentModal
        path="DOCS.md"
        content={"hi"}
        open={false}
        onClose={jest.fn()}
      />,
    );

    expect(screen.queryByTestId("sanitized-markdown")).not.toBeInTheDocument();
    expect(screen.queryByTestId("file-content-modal")).not.toBeInTheDocument();
  });
});
