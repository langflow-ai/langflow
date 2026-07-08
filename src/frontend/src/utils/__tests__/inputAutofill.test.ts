import {
  getSuppressedAutoComplete,
  PASSWORD_MANAGER_IGNORE_PROPS,
  suppressAutofillOnElement,
} from "../inputAutofill";

describe("getSuppressedAutoComplete", () => {
  it("returns new-password for secret fields and off otherwise", () => {
    expect(getSuppressedAutoComplete(true)).toBe("new-password");
    expect(getSuppressedAutoComplete(false)).toBe("off");
  });
});

describe("suppressAutofillOnElement", () => {
  const IGNORE_ATTRS = Object.keys(PASSWORD_MANAGER_IGNORE_PROPS);

  it("stamps autocomplete=off and every password-manager opt-out on an input", () => {
    const input = document.createElement("input");
    suppressAutofillOnElement(input);
    expect(input.getAttribute("autocomplete")).toBe("off");
    expect(input.getAttribute("data-1p-ignore")).toBe("true");
    expect(input.getAttribute("data-lpignore")).toBe("true");
    expect(input.getAttribute("data-bwignore")).toBe("true");
    expect(input.getAttribute("data-form-type")).toBe("other");
  });

  it("works on a textarea (e.g. ag-grid large-text editor)", () => {
    const textarea = document.createElement("textarea");
    suppressAutofillOnElement(textarea);
    for (const attr of IGNORE_ATTRS) {
      expect(textarea.hasAttribute(attr)).toBe(true);
    }
  });

  it("is a no-op when given null/undefined", () => {
    expect(() => suppressAutofillOnElement(null)).not.toThrow();
    expect(() => suppressAutofillOnElement(undefined)).not.toThrow();
  });
});
