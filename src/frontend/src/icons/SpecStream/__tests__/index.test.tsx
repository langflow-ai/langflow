import { render } from "@testing-library/react";
import { createRef } from "react";

// The svg itself lives in SpecStreamIcon.jsx, which the Jest transform does not
// compile; stub it so the wrapper's ref forwarding and prop passthrough are what
// this test exercises.
jest.mock("../SpecStreamIcon", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: (props: Record<string, unknown>) =>
      React.createElement("svg", { "data-testid": "specstream-svg", ...props }),
  };
});

import { SpecStreamIcon } from "../index";

describe("SpecStreamIcon", () => {
  it("forwards the ref and props to the svg component", () => {
    const ref = createRef<SVGSVGElement>();
    const { getByTestId } = render(
      <SpecStreamIcon ref={ref} className="h-4 w-4" aria-label="SpecStream" />,
    );

    const svg = getByTestId("specstream-svg");
    expect(svg).toHaveClass("h-4", "w-4");
    expect(svg).toHaveAttribute("aria-label", "SpecStream");
    expect(ref.current).toBe(svg);
  });
});
