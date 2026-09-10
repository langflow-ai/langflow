import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import SliderComponent from "../index";

/**
 * The slider gradient runs indigo (min) -> pink (max) by default. Threshold
 * sliders where a lower value is stricter opt into `invertGradient` so the
 * pink "hot" end sits on the strict side. jsdom exposes no CSS variables, so
 * the component falls back to its default accent colours here; the assertions
 * compare colours across renders instead of hardcoding a serialisation.
 */

const renderSlider = (value: number, invertGradient?: boolean) => {
  const props: ComponentProps<typeof SliderComponent> = {
    id: "slider_test",
    value: value as never,
    editNode: false,
    disabled: false,
    rangeSpec: { min: 0, max: 1, step: 0.1 },
    handleOnNewValue: jest.fn(),
    invertGradient,
  };
  const { unmount } = render(<SliderComponent {...props} />);
  const thumb = screen.getByTestId("slider_thumb").style.backgroundColor;
  const range = screen.getByTestId("slider_track").firstElementChild;
  const rangeStyle = (range as HTMLElement).getAttribute("style") ?? "";
  unmount();
  return { thumb, rangeStyle };
};

const renderThumbColor = (value: number, invertGradient?: boolean) =>
  renderSlider(value, invertGradient).thumb;

describe("SliderComponent — gradient direction", () => {
  it("swaps the min and max colours when invertGradient is set", () => {
    const defaultMin = renderThumbColor(0);
    const defaultMax = renderThumbColor(1);
    expect(defaultMin).not.toEqual(defaultMax);

    expect(renderThumbColor(0, true)).toEqual(defaultMax);
    expect(renderThumbColor(1, true)).toEqual(defaultMin);
  });

  it("starts the filled range at the colour the other direction ends with", () => {
    // jsdom keeps the inline gradient verbatim, so read its stops as text.
    const stops = (value: number, invert: boolean) =>
      renderSlider(value, invert).rangeStyle.match(
        /to right, (hsl\([^)]*\)) 0%, (hsl\([^)]*\)) \d+%\)/,
      );
    const [, defaultStart] = stops(0, false)!;
    const [, , defaultEnd] = stops(1, false)!;
    const [, invertedStart] = stops(0, true)!;
    const [, , invertedEnd] = stops(1, true)!;

    expect(defaultStart).not.toEqual(defaultEnd);
    expect(invertedStart).toEqual(defaultEnd);
    expect(invertedEnd).toEqual(defaultStart);
  });

  it("keeps the default direction when the flag is absent", () => {
    expect(renderThumbColor(0, false)).toEqual(renderThumbColor(0));
    expect(renderThumbColor(1, false)).toEqual(renderThumbColor(1));
  });
});
