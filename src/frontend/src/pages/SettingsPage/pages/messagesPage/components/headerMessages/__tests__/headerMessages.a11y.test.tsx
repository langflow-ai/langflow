import { render } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import HeaderMessagesComponent from "..";

describe("HeaderMessagesComponent accessibility", () => {
  it("should have no axe violations", async () => {
    const { container } = render(<HeaderMessagesComponent />);

    expect(await axe(container)).toHaveNoViolations();
  });
});
