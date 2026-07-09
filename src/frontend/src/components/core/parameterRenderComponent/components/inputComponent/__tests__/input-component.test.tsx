import { fireEvent, render, screen, within } from "@testing-library/react";
import InputComponent from "../index";

// cmdk calls scrollIntoView on selection; jsdom does not implement it.
Element.prototype.scrollIntoView = jest.fn();

describe("InputComponent — options popover keyboard", () => {
  it("keeps the options popover open when Enter is pressed on the anchor", () => {
    const setSelectedOptions = jest.fn();
    render(
      <InputComponent
        id="apply-to-fields"
        password={false}
        selectedOptions={["System"]}
        setSelectedOptions={setSelectedOptions}
        options={["System", "System Message"]}
        optionsPlaceholder="Fields"
      />,
    );

    const anchor = screen.getByTestId("anchor-popover-anchor-apply-to-fields");
    anchor.focus();
    fireEvent.keyDown(anchor, { key: "Enter", code: "Enter" });

    expect(screen.getByPlaceholderText("Fields")).toBeInTheDocument();
    expect(
      within(screen.getByRole("listbox")).getByText("System Message"),
    ).toBeInTheDocument();
  });
});

describe("InputComponent — FormInputBranch folder-rename synth event", () => {
  it("invokes onChangeFolderName with an event-like object carrying the typed value", () => {
    const onChangeFolderName = jest.fn();
    render(
      <InputComponent
        isForm
        id="folder-input"
        value=""
        password={false}
        onChangeFolderName={onChangeFolderName}
      />,
    );
    const input = screen.getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "new-folder" } });

    expect(onChangeFolderName).toHaveBeenCalledTimes(1);
    const [event] = onChangeFolderName.mock.calls[0];
    expect(event).toMatchObject({
      target: expect.objectContaining({ value: "new-folder" }),
    });
  });

  it("defers the folder-rename synth event until compositionend when IME is active", () => {
    const onChangeFolderName = jest.fn();
    render(
      <InputComponent
        isForm
        id="folder-input"
        value=""
        password={false}
        onChangeFolderName={onChangeFolderName}
      />,
    );
    const input = screen.getByRole("textbox") as HTMLInputElement;

    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: "´" } });
    expect(onChangeFolderName).not.toHaveBeenCalled();

    input.value = "á";
    fireEvent.compositionEnd(input, { data: "á" });

    expect(onChangeFolderName).toHaveBeenCalledTimes(1);
    const [event] = onChangeFolderName.mock.calls[0];
    expect(event.target.value).toBe("á");
  });

  it("falls back to onChange when onChangeFolderName is absent", () => {
    const onChange = jest.fn();
    render(
      <InputComponent
        isForm
        id="plain-input"
        value=""
        password={false}
        onChange={onChange}
      />,
    );
    const input = screen.getByRole("textbox") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "x" } });

    expect(onChange).toHaveBeenCalledWith("x");
  });
});
