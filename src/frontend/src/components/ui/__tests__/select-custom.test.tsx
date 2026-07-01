import { render } from "@testing-library/react";
import * as React from "react";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  SelectContentWithoutPortal,
} from "../select-custom";

describe("Select - Radix Slot 1.3.0 compatibility", () => {
  const renderSelect = () =>
    render(
      <Select>
        <SelectTrigger>
          <SelectValue placeholder="Trigger" />
        </SelectTrigger>
      </Select>,
    );

  it("does not crash when rendering SelectTrigger with Slot composition", () => {
    // Ensures Slot 1.3.0 does not break React element composition
    expect(() => renderSelect()).not.toThrow();
  });

  it("renders trigger with value", () => {
    const { getByText } = renderSelect();

    expect(getByText("Trigger")).toBeInTheDocument();
  });

  it("renders SelectContent without crashing", () => {
    // Ensures Portal + Viewport composition does not throw in runtime
    expect(() =>
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Trigger" />
          </SelectTrigger>

          <SelectContent>
            <SelectItem value="a">A</SelectItem>
          </SelectContent>
        </Select>,
      ),
    ).not.toThrow();
  });

  it("renders SelectItem without crashing in content", () => {
    // Validates forwardRef + ItemText composition safety
    expect(() =>
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Trigger" />
          </SelectTrigger>

          <SelectContentWithoutPortal>
            <SelectItem value="a">A</SelectItem>
          </SelectContentWithoutPortal>
        </Select>,
      ),
    ).not.toThrow();
  });
});
