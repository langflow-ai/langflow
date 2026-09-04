import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { Textarea } from "../textarea";

describe("Textarea accessibility", () => {
  it("should_have_no_axe_violations_when_labeled", async () => {
    const { container } = render(
      <>
        <label htmlFor="prompt">Prompt</label>
        <Textarea id="prompt" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_associate_with_external_label", () => {
    render(
      <>
        <label htmlFor="prompt">Prompt</label>
        <Textarea id="prompt" />
      </>,
    );

    expect(screen.getByRole("textbox", { name: "Prompt" })).toBeInTheDocument();
  });

  it("should_support_aria_label", () => {
    render(<Textarea aria-label="System message" />);

    expect(
      screen.getByRole("textbox", { name: "System message" }),
    ).toBeInTheDocument();
  });
});
