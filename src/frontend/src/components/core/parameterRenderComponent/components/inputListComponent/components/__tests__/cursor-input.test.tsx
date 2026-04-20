import { fireEvent, render, screen } from "@testing-library/react";
import { createRef } from "react";
import { CursorInput } from "../cursor-input";

describe("CursorInput ref forwarding", () => {
  it("populates a React object ref with the underlying input element", () => {
    const ref = createRef<HTMLInputElement>();
    render(
      <CursorInput
        ref={ref}
        value="hello"
        onChange={() => {}}
        dataTestId="cursor-input"
      />,
    );

    expect(ref.current).not.toBeNull();
    expect(ref.current?.tagName).toBe("INPUT");
    expect(ref.current?.value).toBe("hello");
  });

  it("invokes a function ref with the underlying input element", () => {
    const functionRef = jest.fn();
    render(
      <CursorInput
        ref={functionRef}
        value="hi"
        onChange={() => {}}
        dataTestId="cursor-input"
      />,
    );

    expect(functionRef).toHaveBeenCalledTimes(1);
    const [node] = functionRef.mock.calls[0];
    expect(node).toBeInstanceOf(HTMLInputElement);
  });

  it("invokes onFocus and onBlur callbacks", () => {
    const onFocus = jest.fn();
    const onBlur = jest.fn();
    render(
      <CursorInput
        value=""
        onChange={() => {}}
        onFocus={onFocus}
        onBlur={onBlur}
        dataTestId="cursor-input"
      />,
    );
    const input = screen.getByTestId("cursor-input") as HTMLInputElement;

    fireEvent.focus(input);
    fireEvent.blur(input);

    expect(onFocus).toHaveBeenCalledTimes(1);
    expect(onBlur).toHaveBeenCalledTimes(1);
  });

  it("does not throw when onFocus/onBlur are undefined", () => {
    render(
      <CursorInput value="" onChange={() => {}} dataTestId="cursor-input" />,
    );
    const input = screen.getByTestId("cursor-input") as HTMLInputElement;

    expect(() => {
      fireEvent.focus(input);
      fireEvent.blur(input);
    }).not.toThrow();
  });

  it("commits onChange per keystroke when not composing", () => {
    const onChange = jest.fn();
    render(
      <CursorInput value="" onChange={onChange} dataTestId="cursor-input" />,
    );
    const input = screen.getByTestId("cursor-input") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "a" } });
    fireEvent.change(input, { target: { value: "ab" } });

    expect(onChange).toHaveBeenCalledTimes(2);
    expect(onChange).toHaveBeenNthCalledWith(2, "ab");
  });
});
