import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BlockableButton } from "../BlockableButton";

describe("BlockableButton", () => {
  it("runs its action while available", async () => {
    const onClick = jest.fn();
    render(<BlockableButton onClick={onClick}>Replay</BlockableButton>);
    const button = screen.getByRole("button", { name: "Replay" });

    expect(button).not.toHaveAttribute("aria-disabled");
    expect(button).not.toHaveAccessibleDescription();
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("stays focusable, describes why, and ignores clicks while blocked", async () => {
    const onClick = jest.fn();
    render(
      <>
        <button type="button">Before</button>
        <BlockableButton
          blockedReason="Resume the trigger first."
          onClick={onClick}
        >
          Replay
        </BlockableButton>
      </>,
    );
    const button = screen.getByRole("button", { name: "Replay" });

    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription("Resume the trigger first.");
    screen.getByRole("button", { name: "Before" }).focus();
    await userEvent.tab();
    expect(button).toHaveFocus();
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});
