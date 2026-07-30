import { fireEvent, render, screen } from "@testing-library/react";
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

  it("should_keep_accessible_name_and_focus_while_loading", () => {
    // Loading keeps the label via sr-only and stays focusable via aria-disabled
    // (native disabled would drop focus to <body>).
    render(<Button loading>Save flow</Button>);

    const button = screen.getByRole("button", { name: "Save Flow" });
    expect(button).not.toHaveAttribute("disabled");
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAttribute("aria-busy", "true");

    button.focus();
    expect(button).toHaveFocus();
  });

  it("should_retain_focus_when_entering_and_leaving_loading", () => {
    const { rerender } = render(<Button>Save flow</Button>);
    const button = screen.getByRole("button", { name: "Save Flow" });
    button.focus();
    expect(button).toHaveFocus();

    rerender(<Button loading>Save flow</Button>);
    expect(button).toHaveFocus();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveAttribute("aria-disabled", "true");

    rerender(<Button>Save flow</Button>);
    expect(button).toHaveFocus();
    expect(button).not.toHaveAttribute("aria-busy");
    expect(button).not.toHaveAttribute("aria-disabled");
  });

  it("should_ignore_activation_while_loading", () => {
    const onClick = jest.fn();
    render(
      <Button loading onClick={onClick}>
        Save flow
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save Flow" });
    fireEvent.click(button);
    fireEvent.keyDown(button, { key: "Enter" });
    fireEvent.keyDown(button, { key: " " });

    expect(onClick).not.toHaveBeenCalled();
  });

  it("should_prefer_aria_disabled_over_overlapping_disabled_while_loading", () => {
    // Call sites often pass disabled={isLoading} with loading={isLoading}.
    render(
      <Button loading disabled>
        Save flow
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save Flow" });
    expect(button).not.toHaveAttribute("disabled");
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAttribute("aria-busy", "true");

    button.focus();
    expect(button).toHaveFocus();
  });

  it("should_be_disabled_when_disabled", () => {
    render(<Button disabled>Save flow</Button>);

    expect(screen.getByRole("button")).toBeDisabled();
  });
});
