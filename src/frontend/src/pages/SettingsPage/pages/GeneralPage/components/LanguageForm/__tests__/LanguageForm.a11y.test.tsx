import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SUPPORTED_LANGUAGES } from "@/constants/languages";
import { axe } from "@/utils/a11y-test";

const mockLoadLanguage = jest.fn().mockResolvedValue(undefined);

jest.mock("@/i18n", () => ({
  loadLanguage: mockLoadLanguage,
}));

jest.mock("@tanstack/react-query", () => ({
  ...jest.requireActual("@tanstack/react-query"),
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (selector: (s: { setTypes: () => void }) => unknown) =>
    selector({ setTypes: jest.fn() }),
}));

import LanguageFormComponent from "../index";

describe("LanguageForm accessibility", () => {
  beforeAll(() => {
    if (!Element.prototype.hasPointerCapture) {
      Element.prototype.hasPointerCapture = jest.fn(() => false);
    }
    if (!Element.prototype.releasePointerCapture) {
      Element.prototype.releasePointerCapture = jest.fn();
    }
    if (!Element.prototype.scrollIntoView) {
      Element.prototype.scrollIntoView = jest.fn();
    }
  });

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  it("should_have_no_axe_violations_when_closed", async () => {
    const { container } = render(<LanguageFormComponent />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_named_combobox_for_the_language_trigger", () => {
    render(<LanguageFormComponent />);

    expect(
      screen.getByRole("combobox", { name: "Select language" }),
    ).toBeInTheDocument();
  });

  it("should_expose_every_supported_language_as_a_named_option", async () => {
    const user = userEvent.setup();
    render(<LanguageFormComponent />);

    await user.click(screen.getByRole("combobox", { name: "Select language" }));
    await screen.findByRole("listbox");

    SUPPORTED_LANGUAGES.forEach((lang) => {
      expect(
        screen.getByRole("option", { name: new RegExp(lang.label) }),
      ).toBeInTheDocument();
    });
  });

  it("should_open_via_keyboard_and_return_focus_to_the_trigger_on_escape", async () => {
    const user = userEvent.setup();
    render(<LanguageFormComponent />);

    const trigger = screen.getByRole("combobox", { name: "Select language" });
    trigger.focus();
    expect(trigger).toHaveFocus();

    await user.keyboard("{Enter}");
    await screen.findByRole("listbox");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("marks_the_current_language_as_selected_in_the_listbox", async () => {
    const user = userEvent.setup();
    render(<LanguageFormComponent />);

    await user.click(screen.getByRole("combobox", { name: "Select language" }));
    await screen.findByRole("listbox");

    expect(screen.getByRole("option", { name: /English/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});
