import { render } from "@testing-library/react";
import { createRef } from "react";

// The svg itself lives in APIVerveIcon.jsx, which the Jest transform does not
// compile; stub it so the wrapper's ref forwarding and prop passthrough are what
// this test exercises.
jest.mock("../APIVerveIcon", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: (props: Record<string, unknown>) =>
      React.createElement("svg", { "data-testid": "apiverve-svg", ...props }),
  };
});

import { APIVerveIcon } from "../index";

describe("APIVerveIcon", () => {
  it("forwards the ref and props to the svg component", () => {
    const ref = createRef<SVGSVGElement>();
    const { getByTestId } = render(
      <APIVerveIcon ref={ref} className="h-4 w-4" aria-label="APIVerve" />,
    );

    const svg = getByTestId("apiverve-svg");
    expect(svg).toHaveClass("h-4", "w-4");
    expect(svg).toHaveAttribute("aria-label", "APIVerve");
    expect(ref.current).toBe(svg);
  });
});
