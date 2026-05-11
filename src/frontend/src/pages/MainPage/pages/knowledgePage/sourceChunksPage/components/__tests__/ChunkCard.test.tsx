import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

import ChunkCard from "../ChunkCard";

const makeChunk = (overrides = {}) => ({
  id: "chunk-1",
  content: "This is some chunk content for testing.",
  char_count: 39,
  metadata: null,
  ...overrides,
});

describe("ChunkCard", () => {
  describe("Rendering", () => {
    it("renders the chunk index label", () => {
      render(<ChunkCard chunk={makeChunk()} index={3} onCopy={jest.fn()} />);
      expect(screen.getByText("Chunk 3")).toBeInTheDocument();
    });

    it("renders the char_count badge", () => {
      render(
        <ChunkCard
          chunk={makeChunk({ char_count: 128 })}
          index={1}
          onCopy={jest.fn()}
        />,
      );
      expect(screen.getByText("128 chars")).toBeInTheDocument();
    });

    it("renders the chunk content text", () => {
      render(
        <ChunkCard
          chunk={makeChunk({ content: "Hello, world!" })}
          index={1}
          onCopy={jest.fn()}
        />,
      );
      expect(screen.getByText("Hello, world!")).toBeInTheDocument();
    });
  });

  describe("Copy button", () => {
    it("calls onCopy with chunk content when copy button is clicked", async () => {
      const onCopy = jest.fn();
      const user = userEvent.setup();
      render(
        <ChunkCard
          chunk={makeChunk({ content: "Copy this text" })}
          index={1}
          onCopy={onCopy}
        />,
      );
      await user.click(screen.getByRole("button"));
      expect(onCopy).toHaveBeenCalledWith("Copy this text");
    });

    it("shows check icon briefly after copying then reverts", async () => {
      jest.useFakeTimers();
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
      const onCopy = jest.fn();
      render(<ChunkCard chunk={makeChunk()} index={1} onCopy={onCopy} />);

      await user.click(screen.getByRole("button"));

      // Check icon should appear immediately after click
      expect(screen.getByTestId("icon-Check")).toBeInTheDocument();

      // After 2 seconds the copy icon should be restored
      jest.advanceTimersByTime(2100);
      await waitFor(() =>
        expect(screen.queryByTestId("icon-Check")).not.toBeInTheDocument(),
      );

      jest.useRealTimers();
    });
  });
});
