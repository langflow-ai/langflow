import { render } from "@testing-library/react";
import InputComponent from "../index";

/**
 * Locks the autofill scoping for InputComponent:
 *  - node-config fields (the non-form CustomInputPopover path, incl. API-key /
 *    secret fields) suppress autofill so the browser cannot inject saved
 *    credentials that autosave persists;
 *  - real credential forms opt back in via isForm + allowAutofill and must NOT
 *    carry the password-manager opt-out attributes.
 */
describe("InputComponent — autofill scoping", () => {
  const IGNORE_ATTRS = [
    "data-1p-ignore",
    "data-lpignore",
    "data-bwignore",
    "data-form-type",
  ];

  const getInput = (ui: React.ReactElement): HTMLInputElement => {
    const { container } = render(ui);
    const input = container.querySelector("input");
    if (!input) throw new Error("input not found");
    return input;
  };

  it("suppresses autofill with new-password on a node-config secret field", () => {
    const input = getInput(
      <InputComponent id="api_key" value="" password={true} />,
    );
    expect(input.getAttribute("autocomplete")).toBe("new-password");
    for (const attr of IGNORE_ATTRS) {
      expect(input.hasAttribute(attr)).toBe(true);
    }
  });

  it("suppresses autofill with off on a node-config text field", () => {
    const input = getInput(
      <InputComponent id="field" value="" password={false} />,
    );
    expect(input.getAttribute("autocomplete")).toBe("off");
    for (const attr of IGNORE_ATTRS) {
      expect(input.hasAttribute(attr)).toBe(true);
    }
  });

  it("keeps autofill working on a credential form (isForm + allowAutofill) with no opt-outs", () => {
    const input = getInput(
      <InputComponent
        id="login-password"
        value=""
        password={true}
        isForm
        allowAutofill
      />,
    );
    expect(input.getAttribute("autocomplete")).not.toBe("new-password");
    for (const attr of IGNORE_ATTRS) {
      expect(input.hasAttribute(attr)).toBe(false);
    }
  });

  it("still suppresses a form input that does not opt in (e.g. folder rename)", () => {
    const input = getInput(
      <InputComponent id="folder" value="" password={false} isForm />,
    );
    expect(input.getAttribute("autocomplete")).toBe("off");
    expect(input.hasAttribute("data-1p-ignore")).toBe(true);
  });
});
