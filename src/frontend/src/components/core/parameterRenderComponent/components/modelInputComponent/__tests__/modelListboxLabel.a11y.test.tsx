import { render, screen } from "@testing-library/react";
import { Command } from "cmdk";
import ModelList from "../components/ModelList";
import { stripDanglingCmdkLabelFor } from "../index";
import type { ModelOption } from "../types";

/**
 * WCAG 4.1.2 (IBM `label_ref_valid`): the picker renders no CommandInput, and
 * cmdk's `Command label` prop renders a `<label htmlFor={inputId}>` for that
 * input — a label referencing a non-existent element. The accessible name
 * belongs on the CommandList (the listbox) instead. These pin both halves.
 */

window.HTMLElement.prototype.scrollIntoView = jest.fn();

const option = (name: string, provider: string): ModelOption =>
  ({
    name,
    provider,
    enabled: true,
  }) as ModelOption;

const groupedOptions = {
  OpenAI: [option("gpt-4o", "OpenAI")],
};

function renderList(grouped: Record<string, ModelOption[]>) {
  // mirror the real picker: Command gets the same ref callback the
  // component wires, since cmdk renders its dangling label unconditionally
  return render(
    <Command ref={stripDanglingCmdkLabelFor} label="Select a model">
      <ModelList
        groupedOptions={grouped}
        selectedModel={null}
        onSelect={jest.fn()}
      />
    </Command>,
  );
}

describe("model picker listbox accessible name", () => {
  it("names the listbox itself, in both the populated and empty states", () => {
    const { unmount } = renderList(groupedOptions);
    expect(
      screen.getByRole("listbox", { name: "Select a model" }),
    ).toBeInTheDocument();
    unmount();

    renderList({});
    expect(
      screen.getByRole("listbox", { name: "Select a model" }),
    ).toBeInTheDocument();
  });

  it("renders no label that references a non-existent control", () => {
    const { container } = renderList(groupedOptions);
    for (const label of container.querySelectorAll("label[for]")) {
      const target = document.getElementById(label.getAttribute("for")!);
      expect(target).not.toBeNull();
    }
    // cmdk's hidden input-label survives (React owns the node) but must no
    // longer reference the input it never had. It must KEEP its text: an
    // empty label just trades label_ref_valid for label_content_exists,
    // which ignores aria-hidden. Unassociated, it is inert to screen readers.
    expect(container.querySelector("label[cmdk-label][for]")).toBeNull();
    const vestige = container.querySelector("label[cmdk-label]");
    if (vestige) {
      expect(vestige.textContent).not.toBe("");
    }
  });
});
