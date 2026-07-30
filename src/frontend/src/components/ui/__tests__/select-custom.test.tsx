import { render, screen } from "@testing-library/react";

import { Select, SelectTrigger, SelectValue } from "../select-custom";

describe("SelectTrigger", () => {
  it("should render without crashing when the icon has no child", () => {
    render(
      <Select>
        <SelectTrigger aria-label="Test select">
          <SelectValue placeholder="Choose an option" />
        </SelectTrigger>
      </Select>,
    );

    expect(
      screen.getByRole("combobox", { name: "Test select" }),
    ).toBeInTheDocument();
  });
});
