import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { TextEffectPerChar } from "../textAnimation";

// framer-motion's useReducedMotion reads matchMedia once into a module-level
// singleton, so it cannot be toggled per test — stub the hook instead.
let mockReducedMotion = false;
jest.mock("framer-motion", () => ({
  ...jest.requireActual("framer-motion"),
  useReducedMotion: () => mockReducedMotion,
}));

describe("TextEffectPerChar accessibility", () => {
  afterEach(() => {
    mockReducedMotion = false;
  });

  it("has no detectable axe violations", async () => {
    const { container } = render(
      <TextEffectPerChar>Test your flow with a chat prompt</TextEffectPerChar>,
    );

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  it("exposes the full string as one accessible name via role=img", () => {
    render(
      <TextEffectPerChar>Test your flow with a chat prompt</TextEffectPerChar>,
    );

    expect(
      screen.getByRole("img", { name: "Test your flow with a chat prompt" }),
    ).toBeInTheDocument();
  });

  it("renders statically under prefers-reduced-motion", () => {
    mockReducedMotion = true;

    render(
      <TextEffectPerChar>Test your flow with a chat prompt</TextEffectPerChar>,
    );

    const text = screen.getByRole("img", {
      name: "Test your flow with a chat prompt",
    });
    // No per-char animation spans: the string is a single static text node, so
    // there are no opacity-faded intermediate frames to fail contrast checks.
    expect(text.querySelector("span")).toBeNull();
    expect(text).toHaveTextContent("Test your flow with a chat prompt");
  });
});
