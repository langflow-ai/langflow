import { render, screen } from "@testing-library/react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../select-custom";

/**
 * Regression test for SelectPrimitive.Icon.
 *
 * Rendering SelectPrimitive.Icon with `asChild`
 * but without a child element causes a runtime error.
 */
describe("SelectTrigger", () => {
  it("should_render_successfully_with_default_icon", () => {
    expect(() =>
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select option" />
          </SelectTrigger>

          <SelectContent>
            <SelectItem value="1">Option 1</SelectItem>
          </SelectContent>
        </Select>,
      ),
    ).not.toThrow();
  });

  it("should_render_combobox_trigger", () => {
    render(
      <Select>
        <SelectTrigger>
          <SelectValue placeholder="Select option" />
        </SelectTrigger>

        <SelectContent>
          <SelectItem value="1">Option 1</SelectItem>
        </SelectContent>
      </Select>,
    );

    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });
});
