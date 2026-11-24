import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { axe } from "@/utils/a11y-test";
import { SearchInput } from "../searchInput";

describe("SearchInput accessible name", () => {
  const defaultProps = {
    searchInputRef: createRef<HTMLInputElement>(),
    isInputFocused: false,
    search: "",
    handleInputFocus: jest.fn(),
    handleInputBlur: jest.fn(),
    handleInputChange: jest.fn(),
  };

  it("should_have_no_axe_violations", async () => {
    const { container } = render(<SearchInput {...defaultProps} />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("exposes a distinct accessible name that doesn't repeat the word 'Search'", () => {
    render(<SearchInput {...defaultProps} />);

    // The visible placeholder ("Search") is already announced separately as
    // a hint by some screen readers (notably VoiceOver), and the native
    // type="search" role itself is announced as "search text field" — so
    // the aria-label must NOT also contain "Search", or users hear it
    // three times in a row. Keep the name a bare noun instead.
    const input = screen.getByRole("searchbox", { name: "Components" });
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("placeholder", "Search");
  });
});
