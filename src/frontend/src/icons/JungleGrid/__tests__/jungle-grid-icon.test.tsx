import { render } from "@testing-library/react";
import JungleGridIconSvg from "../JungleGridIcon";

describe("JungleGridIconSvg", () => {
  it.each([
    ["true", "#9BFEAA"],
    ["false", "#1A0250"],
  ])("keeps the controlled theme stroke for isdark=%s", (isdark, expectedStroke) => {
    const { container } = render(
      <JungleGridIconSvg isdark={isdark} stroke="#FF0000" />,
    );

    expect(container.querySelector("svg")).toHaveAttribute(
      "stroke",
      expectedStroke,
    );
  });
});
