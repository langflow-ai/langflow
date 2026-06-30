import { render } from "@testing-library/react";
import { Button } from "../button";

describe("Button — loading + asChild", () => {
  it("does not render the loading spinner when rendered asChild", () => {
    const { container } = render(
      <Button loading asChild>
        <a href="/docs">Docs</a>
      </Button>,
    );

    const link = container.querySelector("a");

    expect(link).not.toBeNull();
    expect(link?.textContent).toBe("Docs");

    expect(container.querySelector(".animate-spin")).toBeNull();
  });

  it("renders the loading spinner when loading is enabled on a normal button", () => {
    const { container } = render(<Button loading>Submit</Button>);

    expect(container.querySelector(".animate-spin")).not.toBeNull();
  });
});
