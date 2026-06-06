import { render, screen } from "@testing-library/react";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock(
  "@/components/core/appHeaderComponent/components/LanguageSelector",
  () => ({
    __esModule: true,
    default: ({ triggerClassName }: { triggerClassName?: string }) => (
      <div
        data-testid="language-selector"
        data-trigger-class-name={triggerClassName}
      />
    ),
  }),
);

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
  it("renders the settings language selector", () => {
    render(<LanguageFormComponent />);

    expect(screen.getByText("settings.languageTitle")).toBeInTheDocument();
    expect(
      screen.getByText("settings.languageDescription"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("language-selector")).toHaveAttribute(
      "data-trigger-class-name",
      "w-full",
    );
  });
});
