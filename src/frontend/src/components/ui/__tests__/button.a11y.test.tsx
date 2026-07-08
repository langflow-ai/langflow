import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { Button } from "../button";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  ForwardedIconComponent: () => null,
  default: () => null,
}));

describe("Button accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(<Button>Save flow</Button>);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_button_role_with_accessible_name", () => {
    render(<Button>Save flow</Button>);

    expect(
      screen.getByRole("button", { name: "Save Flow" }),
    ).toBeInTheDocument();
  });

  it("should_keep_accessible_name_while_loading", () => {
    // Loading visually hides the label ("invisible" class) but must keep
    // it in the accessibility tree so the name does not disappear.
    render(<Button loading>Save flow</Button>);

    const button = screen.getByRole("button", { name: "Save Flow" });
    expect(button).toBeDisabled();
  });

  it("should_be_disabled_when_disabled", () => {
    render(<Button disabled>Save flow</Button>);

    expect(screen.getByRole("button")).toBeDisabled();
  });
});
