import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SUPPORTED_LANGUAGES } from "@/constants/languages";

const mockInvalidateQueries = jest.fn();
const mockSetTypes = jest.fn();
const mockChangeLanguage = jest.fn();
const mockLoadLanguage = jest.fn((lang: string) => Promise.resolve(lang));
const mockNormalizeLanguage = jest.fn((lang: string) => lang);
let mockSelectValue: string | undefined;
let mockSelectOnValueChange: ((v: string) => void) | undefined;

jest.mock("@/i18n", () => ({
  loadLanguage: mockLoadLanguage,
  normalizeLanguage: mockNormalizeLanguage,
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { changeLanguage: mockChangeLanguage, language: "en" },
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

  it("renders manual language options in locale file order", () => {
    render(<LanguageSelector />);

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(SUPPORTED_LANGUAGES.length);
    expect(options.map((option) => option.getAttribute("value"))).toEqual([
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
    SUPPORTED_LANGUAGES.forEach((lang) => {
      expect(
        screen.getByRole("option", { name: new RegExp(lang.label) }),
      ).toBeInTheDocument();
    });
  });

  it("selects the current i18n language by default", () => {
    render(<LanguageSelector />);

    expect(screen.getByRole("combobox")).toHaveValue("en");
  });

  it("applies trigger styling props", () => {
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

  it("saves manual selections and refreshes type data", async () => {
    const user = userEvent.setup();
    render(<LanguageSelector />);

    await user.selectOptions(screen.getByRole("combobox"), "de");

    await waitFor(() => {
      expect(localStorage.getItem("languagePreference")).toBe("de");
      expect(mockLoadLanguage).toHaveBeenCalledWith("de");
      expect(mockChangeLanguage).toHaveBeenCalledWith("de");
      expect(mockSetTypes).toHaveBeenCalledWith({});
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetTypes"],
      });
    });
  });
});
