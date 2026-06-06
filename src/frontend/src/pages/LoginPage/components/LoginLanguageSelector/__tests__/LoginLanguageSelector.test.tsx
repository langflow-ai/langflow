import { render, screen } from "@testing-library/react";

const mockLanguageSelector = jest.fn(
  ({
    showIcon,
    triggerClassName,
  }: {
    showIcon?: boolean;
    triggerClassName?: string;
  }) => (
    <div
      data-testid="language-selector"
      data-show-icon={showIcon ? "true" : "false"}
      data-trigger-class-name={triggerClassName}
    />
  ),
);

jest.mock(
  "@/components/core/appHeaderComponent/components/LanguageSelector",
  () => ({
    __esModule: true,
    default: (props: { showIcon?: boolean; triggerClassName?: string }) =>
      mockLanguageSelector(props),
  }),
);

import LoginLanguageSelector from "../index";

describe("LoginLanguageSelector", () => {
  beforeEach(() => {
    mockLanguageSelector.mockClear();
  });

  it("renders the compact login language selector", () => {
    render(<LoginLanguageSelector />);

    expect(screen.getByTestId("language-selector").parentElement).toHaveClass(
      "absolute right-6 top-5 z-10",
    );
    expect(screen.getByTestId("language-selector")).toHaveAttribute(
      "data-show-icon",
      "true",
    );
    expect(screen.getByTestId("language-selector")).toHaveAttribute(
      "data-trigger-class-name",
      "h-9 border-0 bg-transparent px-2 text-sm font-medium text-foreground shadow-none hover:bg-background/60 focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-0",
    );
  });
});
