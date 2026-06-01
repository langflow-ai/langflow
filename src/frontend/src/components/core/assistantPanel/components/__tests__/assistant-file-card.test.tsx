/**
 * F2 — assistant-file-card renders one card per written file.
 *
 * The content arrived inline with the SSE ``file_written`` event, so the
 * card builds the download Blob from the in-memory string — no HTTP fetch.
 * That eliminates the auth / sandbox-path-mismatch failure modes the
 * previous fetch-based design suffered from.
 */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

import { AssistantFileCard } from "../assistant-file-card";
import type { WrittenFile } from "../../assistant-panel.types";

function makeFile(overrides: Partial<WrittenFile> = {}): WrittenFile {
  return {
    action: "write_file",
    path: "FLOW_DOCS.md",
    size: 256,
    receivedAt: 1_700_000_000_000,
    content: "# Hi\n\nBody.",
    ...overrides,
  };
}

beforeEach(() => {
  (global.URL as any).createObjectURL = jest.fn().mockReturnValue("blob:mock");
  (global.URL as any).revokeObjectURL = jest.fn();
});

describe("AssistantFileCard", () => {
  it("should render filename basename", () => {
    render(
      <AssistantFileCard
        file={makeFile({ path: "reports/2026.md" })}
        onOpen={jest.fn()}
      />,
    );
    expect(screen.getByText("2026.md")).toBeInTheDocument();
  });

  it("should render Open and Download buttons with testids scoped to the path", () => {
    const file = makeFile({ path: "FLOW_DOCS.md" });
    render(<AssistantFileCard file={file} onOpen={jest.fn()} />);

    expect(
      screen.getByTestId(`assistant-file-open-button-${file.path}`),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(`assistant-file-download-button-${file.path}`),
    ).toBeInTheDocument();
  });

  it("should call onOpen when Open clicked", () => {
    const onOpen = jest.fn();
    const file = makeFile();
    render(<AssistantFileCard file={file} onOpen={onOpen} />);

    fireEvent.click(
      screen.getByTestId(`assistant-file-open-button-${file.path}`),
    );
    expect(onOpen).toHaveBeenCalledWith(file);
  });

  it("should trigger a Blob download from in-memory content when Download clicked", () => {
    const file = makeFile({ path: "FLOW_DOCS.md", content: "hello" });
    render(<AssistantFileCard file={file} onOpen={jest.fn()} />);

    fireEvent.click(
      screen.getByTestId(`assistant-file-download-button-${file.path}`),
    );

    // createObjectURL is called with the Blob built from `file.content`.
    expect(global.URL.createObjectURL).toHaveBeenCalledTimes(1);
    const blob = (global.URL.createObjectURL as jest.Mock).mock.calls[0][0];
    expect(blob).toBeInstanceOf(Blob);
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock");
  });

  it("should fall through to onOpen when content is undefined (e.g., edit_file)", () => {
    const onOpen = jest.fn();
    const file = makeFile({ action: "edit_file", content: undefined });
    render(<AssistantFileCard file={file} onOpen={onOpen} />);

    fireEvent.click(
      screen.getByTestId(`assistant-file-download-button-${file.path}`),
    );

    // No blob built when there's no content — the modal handles the
    // "preview not available" notice.
    expect(global.URL.createObjectURL).not.toHaveBeenCalled();
    expect(onOpen).toHaveBeenCalledWith(file);
  });

  it("should render edit_file action with a distinct visual cue", () => {
    const file = makeFile({ action: "edit_file", path: "DOCS.md" });
    render(<AssistantFileCard file={file} onOpen={jest.fn()} />);

    const root = screen.getByTestId(`assistant-file-card-${file.path}`);
    expect(root.getAttribute("data-action")).toBe("edit_file");
  });
});
