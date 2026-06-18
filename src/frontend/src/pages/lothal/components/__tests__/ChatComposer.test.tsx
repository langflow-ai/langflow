import { fireEvent, render } from "@testing-library/react";
import { createRef } from "react";
import { ChatComposer, type ChatComposerHandle } from "../ChatComposer";
import type { Anchor } from "../d2/anchor";

const editorOf = (c: HTMLElement) =>
  c.querySelector(".lothal-composer-editor") as HTMLElement;

describe("ChatComposer", () => {
  it("shows the placeholder via data-placeholder", () => {
    const { container } = render(
      <ChatComposer onSend={jest.fn()} placeholder="Say something…" />,
    );
    expect(editorOf(container).dataset.placeholder).toBe("Say something…");
  });

  it("insertAnchor drops an inline chip carrying the exact anchor id", () => {
    const ref = createRef<ChatComposerHandle>();
    const { container } = render(<ChatComposer ref={ref} onSend={jest.fn()} />);
    ref.current!.insertAnchor({
      kind: "node",
      id: "checkout",
      label: "Checkout",
    });

    const chip = editorOf(container).querySelector(
      ".lothal-chip",
    ) as HTMLElement;
    expect(chip).toBeTruthy();
    expect(chip.dataset.id).toBe("checkout");
    expect(chip.dataset.kind).toBe("node");
    expect(chip.textContent).toContain("Checkout");
  });

  it("serializes text + chips to the message, each chip as a backtick anchor id", () => {
    const onSend = jest.fn();
    const ref = createRef<ChatComposerHandle>();
    const { container } = render(<ChatComposer ref={ref} onSend={onSend} />);
    const editor = editorOf(container);

    ref.current!.insertAnchor({
      kind: "node",
      id: "checkout",
      label: "Checkout",
    });
    // Simulate the user typing before the chip (contentEditable: drive the DOM).
    editor.insertBefore(document.createTextNode("rename "), editor.firstChild);

    fireEvent.click(container.querySelector(".lothal-composer-send")!);
    expect(onSend).toHaveBeenCalledWith("rename `checkout`");
    // Cleared after send.
    expect(editor.textContent).toBe("");
  });

  it("serializes a parallel-edge chip with its disambiguating index", () => {
    const onSend = jest.fn();
    const ref = createRef<ChatComposerHandle>();
    const { container } = render(<ChatComposer ref={ref} onSend={onSend} />);
    const anchor: Anchor = {
      kind: "edge",
      id: "user → db #2",
      label: "sync",
      src: "user",
      dst: "db",
      index: 1,
    };
    ref.current!.insertAnchor(anchor);
    fireEvent.click(container.querySelector(".lothal-composer-send")!);
    expect(onSend).toHaveBeenCalledWith("`user → db #2`");
  });

  it("sends on Enter (not Shift+Enter)", () => {
    const onSend = jest.fn();
    const { container } = render(<ChatComposer onSend={onSend} />);
    const editor = editorOf(container);
    editor.appendChild(document.createTextNode("a tide app"));

    fireEvent.keyDown(editor, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();

    fireEvent.keyDown(editor, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("a tide app");
  });

  it("does not send when empty", () => {
    const onSend = jest.fn();
    const { container } = render(<ChatComposer onSend={onSend} />);
    fireEvent.click(container.querySelector(".lothal-composer-send")!);
    fireEvent.keyDown(editorOf(container), { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not send while disabled", () => {
    const onSend = jest.fn();
    const { container } = render(<ChatComposer onSend={onSend} disabled />);
    const editor = editorOf(container);
    editor.appendChild(document.createTextNode("queued"));
    fireEvent.keyDown(editor, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not insert a chip while disabled", () => {
    const ref = createRef<ChatComposerHandle>();
    const { container } = render(
      <ChatComposer ref={ref} onSend={jest.fn()} disabled />,
    );
    ref.current!.insertAnchor({
      kind: "node",
      id: "checkout",
      label: "Checkout",
    });
    expect(editorOf(container).querySelector(".lothal-chip")).toBeNull();
  });

  it("preserves newlines (Shift+Enter) and serializes chips nested in a block", () => {
    const onSend = jest.fn();
    const { container } = render(<ChatComposer onSend={onSend} />);
    const editor = editorOf(container);
    // Mimic the DOM a contentEditable produces for "line one\nrename [chip]":
    // a <br> then a block container holding text + a chip.
    editor.appendChild(document.createTextNode("line one"));
    editor.appendChild(document.createElement("br"));
    const block = document.createElement("div");
    block.appendChild(document.createTextNode("rename "));
    const chip = document.createElement("span");
    chip.className = "lothal-chip";
    chip.dataset.id = "checkout";
    chip.textContent = "▭ Checkout";
    block.appendChild(chip);
    editor.appendChild(block);

    fireEvent.click(container.querySelector(".lothal-composer-send")!);
    expect(onSend).toHaveBeenCalledWith("line one\nrename `checkout`");
  });
});
