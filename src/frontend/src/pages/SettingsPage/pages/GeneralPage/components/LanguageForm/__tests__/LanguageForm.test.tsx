import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SUPPORTED_LANGUAGES } from "@/constants/languages";

const mockChangeLanguage = jest.fn();
const mockInvalidateQueries = jest.fn();
const mockSetTypes = jest.fn();
const mockLoadLanguage = jest.fn().mockResolvedValue(undefined);

jest.mock("@/i18n", () => ({
  loadLanguage: mockLoadLanguage,
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { changeLanguage: mockChangeLanguage, language: "en" },
  }),
}));

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (
    selector: (s: { setTypes: typeof mockSetTypes }) => unknown,
  ) => selector({ setTypes: mockSetTypes }),
}));

jest.mock("@/components/ui/card", () => ({
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CardTitle: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CardDescription: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CardContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

import LanguageFormComponent from "../index";

describe("LanguageFormComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  it("renders all supported language options", () => {
    render(<LanguageFormComponent />);
    const select = screen.getByRole("combobox");
    const options = select.querySelectorAll("option");
    expect(options).toHaveLength(SUPPORTED_LANGUAGES.length);
    SUPPORTED_LANGUAGES.forEach((lang) => {
      expect(
        screen.getByRole("option", { name: new RegExp(lang.label) }),
      ).toBeInTheDocument();
    });
  });

  it("calls i18n.changeLanguage with the selected language code", async () => {
    const user = userEvent.setup();
    render(<LanguageFormComponent />);
    await user.selectOptions(screen.getByRole("combobox"), "fr");
    expect(mockChangeLanguage).toHaveBeenCalledWith("fr");
  });

  it("saves selected language to localStorage", async () => {
    const user = userEvent.setup();
    render(<LanguageFormComponent />);
    await user.selectOptions(screen.getByRole("combobox"), "ja");
    expect(localStorage.getItem("languagePreference")).toBe("ja");
  });

  it("calls setTypes with empty object on language change", async () => {
    const user = userEvent.setup();
    render(<LanguageFormComponent />);
    await user.selectOptions(screen.getByRole("combobox"), "de");
    expect(mockSetTypes).toHaveBeenCalledWith({});
  });

  it("invalidates useGetTypes query on language change", async () => {
    const user = userEvent.setup();
    render(<LanguageFormComponent />);
    await user.selectOptions(screen.getByRole("combobox"), "es");
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetTypes"],
    });
  });

  it("shows recommended label for English option", () => {
    render(<LanguageFormComponent />);
    const enOption = screen.getByRole("option", { name: /English/i });
    expect(enOption.textContent).toContain("settings.languageRecommended");
  });

  it("does not show recommended label for non-English options", () => {
    render(<LanguageFormComponent />);
    const frOption = screen.getByRole("option", { name: /Français/i });
    expect(frOption.textContent).not.toContain("settings.languageRecommended");
  });

  it("calls loadLanguage before changeLanguage when switching languages", async () => {
    const user = userEvent.setup();
    render(<LanguageFormComponent />);
    await user.selectOptions(screen.getByRole("combobox"), "fr");
    expect(mockLoadLanguage).toHaveBeenCalledWith("fr");
    expect(mockChangeLanguage).toHaveBeenCalledWith("fr");
  });
});
