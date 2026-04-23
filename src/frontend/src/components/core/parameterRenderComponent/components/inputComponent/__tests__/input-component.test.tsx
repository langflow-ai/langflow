import { fireEvent, render, screen } from "@testing-library/react";
import InputComponent from "../index";

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
