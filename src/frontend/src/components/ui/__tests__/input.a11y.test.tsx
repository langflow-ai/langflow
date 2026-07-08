import { render, screen } from "@testing-library/react";
import { Input } from "../input";

describe("Input accessibility", () => {
  it("should_render_textbox", () => {
    render(<Input placeholder="Search flows" />);

    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  // Known gap (a11y-action-plan 1.2): Input wraps the <input> in a <label>
  // containing the visual placeholder span, so an externally labeled field
  // gets a polluted accessible name (external label + placeholder text).
  it("should_use_only_external_label_as_accessible_name", () => {
    render(
      <>
        <label htmlFor="username">Username</label>
        <Input id="username" placeholder="Type your username" />
      </>,
    );

    expect(
      screen.getByRole("textbox", { name: "Username" }),
    ).toBeInTheDocument();
  });

  it("should_hide_visual_placeholder_span_from_AT", () => {
    render(<Input placeholder="Search flows" />);

    const placeholderSpan = screen.getByText("Search flows", {
      selector: "span",
    });
    expect(placeholderSpan).toHaveAttribute("aria-hidden", "true");
  });
});
