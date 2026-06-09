import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AUTO_LANGUAGE, SUPPORTED_LANGUAGES } from "@/constants/languages";

const mockInvalidateQueries = jest.fn();
const mockSetTypes = jest.fn();
const mockLoadLanguage = jest.fn().mockResolvedValue("en");
const mockGetBrowserLanguage = jest.fn(() => "zh-Hans");
const mockNormalizeLanguage = jest.fn((lang: string) =>
  lang === "fr-FR" ? "fr" : lang,
);
let mockSelectValue: string | undefined;
let mockSelectOnValueChange: ((v: string) => void) | undefined;

jest.mock("@/i18n", () => ({
  getBrowserLanguage: mockGetBrowserLanguage,
  loadLanguage: mockLoadLanguage,
  normalizeLanguage: mockNormalizeLanguage,
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@tanstack/react-query", () => ({
  ...jest.requireActual("@tanstack/react-query"),
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (
    selector: (state: { setTypes: typeof mockSetTypes }) => unknown,
  ) => selector({ setTypes: mockSetTypes }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span data-testid={name} />,
}));

jest.mock("@/components/ui/select", () => ({
  Select: ({
    children,
    value,
    onValueChange,
  }: {
    children: React.ReactNode;
    value?: string;
    onValueChange?: (v: string) => void;
  }) => {
    mockSelectValue = value;
    mockSelectOnValueChange = onValueChange;

    return <div>{children}</div>;
  },
  SelectTrigger: ({
    children,
    className,
    "aria-label": ariaLabel,
  }: {
    children: React.ReactNode;
    className?: string;
    "aria-label"?: string;
  }) => (
    <button
      aria-label={ariaLabel}
      className={className}
      data-testid="select-trigger"
      type="button"
    >
      {children}
    </button>
  ),
  SelectValue: () => null,
  SelectContent: ({ children }: { children: React.ReactNode }) => (
    <select
      aria-label="settings.languageSelectAriaLabel"
      value={mockSelectValue}
      onChange={(event) => mockSelectOnValueChange?.(event.target.value)}
    >
      {children}
    </select>
  ),
  SelectItem: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) => <option value={value}>{children}</option>,
}));

import LanguageSelector from "../index";

describe("LanguageSelector", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    mockSelectValue = undefined;
    mockSelectOnValueChange = undefined;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("renders Auto plus manual language options in locale file order", () => {
    render(<LanguageSelector />);

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(SUPPORTED_LANGUAGES.length + 1);
    expect(options.map((option) => option.getAttribute("value"))).toEqual([
      AUTO_LANGUAGE,
      "de",
      "en",
      "es",
      "fr",
      "ja",
      "ko",
      "pt",
      "ru",
      "zh-Hans",
    ]);
    expect(
      screen.getByRole("option", { name: /settings.languageAuto/i }),
    ).toBeInTheDocument();
    SUPPORTED_LANGUAGES.forEach((lang) => {
      expect(
        screen.getByRole("option", { name: new RegExp(lang.label) }),
      ).toBeInTheDocument();
    });
  });

  it("selects Auto by default", () => {
    render(<LanguageSelector />);

    expect(screen.getByRole("combobox")).toHaveValue(AUTO_LANGUAGE);
  });

  it("applies trigger styling and icon props", () => {
    render(
      <LanguageSelector
        className="selector-shell"
        showIcon
        triggerClassName="selector-trigger"
      />,
    );

    expect(screen.getByTestId("select-trigger")).toHaveClass(
      "selector-shell",
      "selector-trigger",
    );
    expect(screen.getByTestId("Globe")).toBeInTheDocument();
  });

  it("normalizes stored manual preferences before displaying them", () => {
    localStorage.setItem("languagePreference", "fr-FR");

    render(<LanguageSelector />);

    expect(mockNormalizeLanguage).toHaveBeenCalledWith("fr-FR");
    expect(screen.getByRole("combobox")).toHaveValue("fr");
  });

  it("falls back to Auto when stored preference cannot be read", () => {
    jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("Storage unavailable");
    });

    expect(() => render(<LanguageSelector />)).not.toThrow();
    expect(screen.getByRole("combobox")).toHaveValue(AUTO_LANGUAGE);
  });

  it("saves manual selections and refreshes type data", async () => {
    const user = userEvent.setup();
    render(<LanguageSelector />);

    await user.selectOptions(screen.getByRole("combobox"), "de");

    await waitFor(() => {
      expect(localStorage.getItem("languagePreference")).toBe("de");
      expect(mockLoadLanguage).toHaveBeenCalledWith("de");
      expect(mockSetTypes).toHaveBeenCalledWith({});
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetTypes"],
      });
    });
  });

  it("continues switching manual languages when persistence fails", async () => {
    const user = userEvent.setup();
    jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("Storage unavailable");
    });
    render(<LanguageSelector />);

    await user.selectOptions(screen.getByRole("combobox"), "de");

    await waitFor(() => {
      expect(mockLoadLanguage).toHaveBeenCalledWith("de");
      expect(mockSetTypes).toHaveBeenCalledWith({});
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetTypes"],
      });
    });
  });

  it("clears manual preference and loads browser language when selecting Auto", async () => {
    const user = userEvent.setup();
    localStorage.setItem("languagePreference", "fr");

    render(<LanguageSelector />);
    await user.selectOptions(screen.getByRole("combobox"), AUTO_LANGUAGE);

    await waitFor(() => {
      expect(localStorage.getItem("languagePreference")).toBeNull();
      expect(mockGetBrowserLanguage).toHaveBeenCalled();
      expect(mockLoadLanguage).toHaveBeenCalledWith("zh-Hans");
      expect(mockSetTypes).toHaveBeenCalledWith({});
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetTypes"],
      });
    });
  });

  it("continues switching to Auto when persistence cleanup fails", async () => {
    const user = userEvent.setup();
    localStorage.setItem("languagePreference", "fr");
    jest.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("Storage unavailable");
    });

    render(<LanguageSelector />);
    await user.selectOptions(screen.getByRole("combobox"), AUTO_LANGUAGE);

    await waitFor(() => {
      expect(mockGetBrowserLanguage).toHaveBeenCalled();
      expect(mockLoadLanguage).toHaveBeenCalledWith("zh-Hans");
      expect(mockSetTypes).toHaveBeenCalledWith({});
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetTypes"],
      });
    });
  });
});
