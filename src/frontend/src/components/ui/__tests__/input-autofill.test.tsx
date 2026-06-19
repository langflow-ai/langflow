import { render } from "@testing-library/react";
import { Input } from "../input";

/**
 * Guards the autofill-suppression contract of the base Input primitive.
 *
 * Browsers (notably Chrome) ignore autocomplete="off" for credential-like
 * fields and inject saved values that Langflow's autosave then persists,
 * corrupting flows. The primitive therefore suppresses autofill by default and
 * only opts back in for real credential forms via `allowAutofill`.
 */
describe("Input — autofill suppression", () => {
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

  it("suppresses autofill by default on a text field (off + password-manager opt-outs)", () => {
    const input = getInput(<Input placeholder="name" />);
    expect(input.getAttribute("autocomplete")).toBe("off");
    expect(input.getAttribute("data-1p-ignore")).toBe("true");
    expect(input.getAttribute("data-lpignore")).toBe("true");
    expect(input.getAttribute("data-bwignore")).toBe("true");
    expect(input.getAttribute("data-form-type")).toBe("other");
  });

  it("uses new-password on a password/secret field so Chrome won't inject a saved credential", () => {
    const input = getInput(<Input type="password" placeholder="API Key" />);
    expect(input.getAttribute("autocomplete")).toBe("new-password");
    for (const attr of IGNORE_ATTRS) {
      expect(input.hasAttribute(attr)).toBe(true);
    }
  });

  it("opts back into autofill (no autocomplete attr, no password-manager opt-outs) when allowAutofill is set", () => {
    const input = getInput(<Input allowAutofill placeholder="username" />);
    // With no explicit autoComplete, an opted-in field emits no attribute so
    // the browser applies its normal (wanted) autofill behavior.
    expect(input.getAttribute("autocomplete")).toBeNull();
    for (const attr of IGNORE_ATTRS) {
      expect(input.hasAttribute(attr)).toBe(false);
    }
  });

  it("does NOT force new-password on an allowAutofill password field (real login password)", () => {
    const input = getInput(<Input allowAutofill type="password" />);
    expect(input.getAttribute("autocomplete")).not.toBe("new-password");
    for (const attr of IGNORE_ATTRS) {
      expect(input.hasAttribute(attr)).toBe(false);
    }
  });

  it("honors an explicit autoComplete on an allowAutofill field (e.g. username/current-password)", () => {
    const input = getInput(
      <Input allowAutofill autoComplete="current-password" />,
    );
    expect(input.getAttribute("autocomplete")).toBe("current-password");
  });

  it("lets a caller-provided autoComplete win over the suppressed default", () => {
    const input = getInput(<Input autoComplete="email" />);
    expect(input.getAttribute("autocomplete")).toBe("email");
  });
});
