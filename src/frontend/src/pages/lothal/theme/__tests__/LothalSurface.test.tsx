import { fireEvent, render, screen } from "@testing-library/react";
import { LothalSurface, useLothalTheme } from "../LothalSurface";

// A tiny consumer that surfaces the current theme/density and lets the test
// drive the setters — enough to assert the localStorage round-trip.
function Probe() {
  const { theme, density, setTheme, setDensity } = useLothalTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="density">{density}</span>
      <button type="button" onClick={() => setTheme("light")}>
        light
      </button>
      <button type="button" onClick={() => setDensity("compact")}>
        compact
      </button>
    </div>
  );
}

describe("LothalSurface appearance persistence", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("writes the theme and density to localStorage when changed", () => {
    render(
      <LothalSurface>
        <Probe />
      </LothalSurface>,
    );
    fireEvent.click(screen.getByText("light"));
    fireEvent.click(screen.getByText("compact"));
    expect(window.localStorage.getItem("lothal:theme")).toBe("light");
    expect(window.localStorage.getItem("lothal:density")).toBe("compact");
  });

  it("seeds the initial theme/density from a previous session", () => {
    window.localStorage.setItem("lothal:theme", "light");
    window.localStorage.setItem("lothal:density", "comfy");
    render(
      <LothalSurface>
        <Probe />
      </LothalSurface>,
    );
    expect(screen.getByTestId("theme")).toHaveTextContent("light");
    expect(screen.getByTestId("density")).toHaveTextContent("comfy");
  });

  it("ignores a corrupt stored value and falls back to the default", () => {
    window.localStorage.setItem("lothal:theme", "chartreuse");
    render(
      <LothalSurface>
        <Probe />
      </LothalSurface>,
    );
    // Default surface theme is dark; the bogus value must not leak through.
    expect(screen.getByTestId("theme")).toHaveTextContent("dark");
  });
});
