import { render } from "@testing-library/react";
import { createRef } from "react";

// The svg itself lives in GetYouTubeTranscriptIcon.jsx, which the Jest transform does not
// compile; stub it so the wrapper's ref forwarding and prop passthrough are what
// this test exercises.
jest.mock("../GetYouTubeTranscriptIcon", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: (props: Record<string, unknown>) =>
      React.createElement("svg", {
        "data-testid": "getyoutubetranscript-svg",
        ...props,
      }),
  };
});

import { GetYouTubeTranscriptIcon } from "../index";

describe("GetYouTubeTranscriptIcon", () => {
  it("forwards the ref and props to the svg component", () => {
    const ref = createRef<SVGSVGElement>();
    const { getByTestId } = render(
      <GetYouTubeTranscriptIcon
        ref={ref}
        className="h-4 w-4"
        aria-label="GetYouTubeTranscript"
      />,
    );

    const svg = getByTestId("getyoutubetranscript-svg");
    expect(svg).toHaveClass("h-4", "w-4");
    expect(svg).toHaveAttribute("aria-label", "GetYouTubeTranscript");
    expect(ref.current).toBe(svg);
  });
});
