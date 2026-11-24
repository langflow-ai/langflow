import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "../button";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  ForwardedIconComponent: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

describe("Button behavior", () => {
  it("fires onClick when enabled", async () => {
    const onClick = jest.fn();
    const user = userEvent.setup();
    render(<Button onClick={onClick}>Save</Button>);

    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("does not fire onClick when disabled", async () => {
    const onClick = jest.fn();
    const user = userEvent.setup();
    render(
      <Button disabled onClick={onClick}>
        Save
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("disabled");
    await user.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("blocks activation while loading without native disabled", () => {
    const onClick = jest.fn();
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save" });
    expect(button).not.toHaveAttribute("disabled");
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(screen.getByTestId("icon-Loader2")).toBeInTheDocument();

    fireEvent.click(button);
    fireEvent.keyDown(button, { key: "Enter" });
    fireEvent.keyDown(button, { key: " " });
    expect(onClick).not.toHaveBeenCalled();
  });

  it("blocks activation when loading overlaps disabled prop", () => {
    const onClick = jest.fn();
    render(
      <Button loading disabled onClick={onClick}>
        Save
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save" });
    expect(button).not.toHaveAttribute("disabled");
    expect(button).toHaveAttribute("aria-disabled", "true");

    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("restores interactivity after loading ends", async () => {
    const onClick = jest.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    );

    rerender(<Button onClick={onClick}>Save</Button>);

    const button = screen.getByRole("button", { name: "Save" });
    expect(button).not.toHaveAttribute("aria-busy");
    expect(button).not.toHaveAttribute("aria-disabled");
    await user.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("defaults type to button so it does not submit forms accidentally", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute(
      "type",
      "button",
    );
  });

  it("preserves explicit submit type when not loading", () => {
    render(<Button type="submit">Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute(
      "type",
      "submit",
    );
  });

  it("forwards ref to the underlying button element", () => {
    const ref = { current: null as HTMLButtonElement | null };
    render(<Button ref={ref}>Save</Button>);
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
    expect(ref.current).toHaveTextContent("Save");
  });

  it("applies title case to string children by default", () => {
    render(<Button>save flow</Button>);
    expect(
      screen.getByRole("button", { name: "Save Flow" }),
    ).toBeInTheDocument();
  });

  it("can skip title case when ignoreTitleCase is set", () => {
    render(<Button ignoreTitleCase>save flow</Button>);
    expect(
      screen.getByRole("button", { name: "save flow" }),
    ).toBeInTheDocument();
  });
});
