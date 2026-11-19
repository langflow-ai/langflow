import { render, screen } from "@testing-library/react";
import { TextShimmer } from "../TextShimmer";

describe("TextShimmer", () => {
  // A re-render must keep the same DOM node, or the animation restarts.
  it("keeps the same DOM node when the parent re-renders", () => {
    const { rerender } = render(<TextShimmer>Running flow</TextShimmer>);
    const before = screen.getByText("Running flow");

    rerender(<TextShimmer>Running flow</TextShimmer>);

    expect(screen.getByText("Running flow")).toBe(before);
  });

  // A new `as` value must render the new tag.
  it("renders the new tag when `as` changes", () => {
    const { rerender } = render(<TextShimmer as="p">Running flow</TextShimmer>);
    expect(screen.getByText("Running flow").tagName).toBe("P");

    rerender(<TextShimmer as="span">Running flow</TextShimmer>);

    expect(screen.getByText("Running flow").tagName).toBe("SPAN");
  });
});
