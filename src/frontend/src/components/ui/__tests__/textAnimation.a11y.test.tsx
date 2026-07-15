import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { TextEffectPerChar } from "../textAnimation";

describe("TextEffectPerChar accessibility", () => {
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
});
