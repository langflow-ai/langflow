import { render } from "@testing-library/react";
import { createRef } from "react";

// The svg itself lives in LinkupIcon.jsx, which the Jest transform does not
// compile; stub it so the wrapper's ref forwarding and prop passthrough are what
// this test exercises.
jest.mock("../LinkupIcon", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: (props: Record<string, unknown>) =>
      React.createElement("svg", { "data-testid": "linkup-svg", ...props }),
  };
});

import { LinkupIcon } from "../index";

describe("LinkupIcon", () => {
  it("forwards the ref and props to the svg component", () => {
    const ref = createRef<SVGSVGElement>();
    const { getByTestId } = render(
      <LinkupIcon ref={ref} className="h-4 w-4" aria-label="Linkup" />,
    );

    const svg = getByTestId("linkup-svg");
    expect(svg).toHaveClass("h-4", "w-4");
    expect(svg).toHaveAttribute("aria-label", "Linkup");
    expect(ref.current).toBe(svg);
  });
});
