import { render, screen } from "@testing-library/react";
import CustomLoginBrandTitle from "../custom-login-brand-title";

describe("CustomLoginBrandTitle", () => {
  it("renders the OSS product name", () => {
    render(<CustomLoginBrandTitle />);

    expect(screen.getByText("Langflow")).toBeInTheDocument();
  });
});
