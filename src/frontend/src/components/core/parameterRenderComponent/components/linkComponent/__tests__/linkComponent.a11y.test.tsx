import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import LinkComponent from "../index";

jest.mock("@/customization/utils/custom-open-new-tab", () => ({
  customOpenNewTab: jest.fn(),
}));

const baseProps = {
  value: "example.com",
  disabled: false,
  id: "link-field",
  editNode: false,
  handleOnNewValue: jest.fn(),
};

describe("LinkComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="link-label">Documentation</span>
        <LinkComponent {...baseProps} ariaLabelledBy="link-label" />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_fall_back_to_the_forwarded_field_label_when_the_button_is_icon_only", () => {
    render(
      <>
        <span id="link-label">Documentation</span>
        <LinkComponent {...baseProps} ariaLabelledBy="link-label" />
      </>,
    );
    expect(
      screen.getByRole("button", { name: "Documentation" }),
    ).toBeInTheDocument();
  });

  it("should_not_override_visible_button_text_with_the_forwarded_field_label", () => {
    render(
      <>
        <span id="link-label">Documentation</span>
        <LinkComponent
          {...baseProps}
          text="Open docs"
          ariaLabelledBy="link-label"
        />
      </>,
    );
    // A visible label ("Open docs") is a better accessible name than the
    // generic field label, so aria-labelledby must not be applied here.
    expect(
      screen.getByRole("button", { name: "Open docs" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Documentation")).not.toBeNull(); // still rendered, just not referenced
  });
});
