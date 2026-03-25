import { render } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockSvg = jest.fn((props) => (
  <svg data-testid="youdotcom-icon" {...props} />
));
mockSvg.displayName = "YouDotCom";

jest.mock("./YouDotCom", () => ({
  __esModule: true,
  default: mockSvg,
}));

jest.mock("./index", () => ({
  __esModule: true,
  YouDotComIcon: mockSvg,
}));

import YouDotCom from "./YouDotCom";
import { YouDotComIcon } from "./index";

describe("YouDotCom", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders without crashing", () => {
    const { container } = render(<YouDotCom />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("accepts additional props", () => {
    const { container } = render(<YouDotCom data-testid="youdotcom-icon" />);
    expect(
      container.querySelector('[data-testid="youdotcom-icon"]'),
    ).toBeInTheDocument();
  });

  it("has correct displayName", () => {
    expect(YouDotCom.displayName).toBe("YouDotCom");
  });
});

describe("YouDotComIcon", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders without crashing", () => {
    const { container } = render(<YouDotComIcon />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("accepts additional props", () => {
    const { container } = render(
      <YouDotComIcon data-testid="youdotcom-icon-wrapper" />,
    );
    expect(
      container.querySelector('[data-testid="youdotcom-icon-wrapper"]'),
    ).toBeInTheDocument();
  });
});
