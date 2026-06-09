import { fireEvent, render, screen } from "@testing-library/react";
import VisibilityToggleButton from "../VisibilityToggleButton";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  ForwardedIconComponent: ({
    name,
    className,
  }: {
    name: string;
    className?: string;
  }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

const defaultProps = {
  id: "showtemplate",
  checked: true,
  disabled: false,
  onToggle: jest.fn(),
};

describe("VisibilityToggleButton", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Happy path tests

  it("should_render_eye_icon_when_checked_is_true", () => {
    render(<VisibilityToggleButton {...defaultProps} checked={true} />);

    expect(screen.getByTestId("icon-Eye")).toBeInTheDocument();
    expect(screen.queryByTestId("icon-EyeOff")).not.toBeInTheDocument();
  });

  it("should_render_eyeoff_icon_when_checked_is_false", () => {
    render(<VisibilityToggleButton {...defaultProps} checked={false} />);

    expect(screen.getByTestId("icon-EyeOff")).toBeInTheDocument();
    expect(screen.queryByTestId("icon-Eye")).not.toBeInTheDocument();
  });

  it("should_call_onToggle_when_clicked", () => {
    const onToggle = jest.fn();
    render(<VisibilityToggleButton {...defaultProps} onToggle={onToggle} />);

    fireEvent.click(screen.getByTestId("showtemplate"));

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("should_have_correct_data_testid", () => {
    render(<VisibilityToggleButton {...defaultProps} id="showpath" />);

    expect(screen.getByTestId("showpath")).toBeInTheDocument();
  });

  it("should_have_correct_id_attribute", () => {
    render(<VisibilityToggleButton {...defaultProps} id="showpath" />);

    const button = screen.getByTestId("showpath");
    expect(button.id).toBe("showpath");
  });

  it("should_have_role_switch", () => {
    render(<VisibilityToggleButton {...defaultProps} />);

    expect(screen.getByRole("switch")).toBeInTheDocument();
  });

  it("should_have_aria_checked_true_when_checked", () => {
    render(<VisibilityToggleButton {...defaultProps} checked={true} />);

    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });

  it("should_have_aria_checked_false_when_unchecked", () => {
    render(<VisibilityToggleButton {...defaultProps} checked={false} />);

    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  });

  // Adversarial tests

  it("should_be_disabled_when_disabled_prop_is_true", () => {
    render(<VisibilityToggleButton {...defaultProps} disabled={true} />);

    expect(screen.getByRole("switch")).toBeDisabled();
  });

  it("should_not_call_onToggle_when_disabled_and_clicked", () => {
    const onToggle = jest.fn();
    render(
      <VisibilityToggleButton
        {...defaultProps}
        disabled={true}
        onToggle={onToggle}
      />,
    );

    fireEvent.click(screen.getByTestId("showtemplate"));

    expect(onToggle).not.toHaveBeenCalled();
  });

  it("should_stop_event_propagation_on_click", () => {
    const parentOnClick = jest.fn();
    render(
      <div onClick={parentOnClick}>
        <VisibilityToggleButton {...defaultProps} />
      </div>,
    );

    fireEvent.click(screen.getByTestId("showtemplate"));

    expect(parentOnClick).not.toHaveBeenCalled();
  });

  it("should_have_hide_aria_label_when_checked", () => {
    render(<VisibilityToggleButton {...defaultProps} checked={true} />);

    expect(screen.getByRole("switch")).toHaveAttribute(
      "aria-label",
      "Hide field",
    );
  });

  it("should_have_show_aria_label_when_unchecked", () => {
    render(<VisibilityToggleButton {...defaultProps} checked={false} />);

    expect(screen.getByRole("switch")).toHaveAttribute(
      "aria-label",
      "Show field",
    );
  });
});
