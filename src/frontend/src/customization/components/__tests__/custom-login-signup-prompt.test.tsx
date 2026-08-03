import { render, screen } from "@testing-library/react";
import CustomLoginSignupPrompt from "../custom-login-signup-prompt";

describe("CustomLoginSignupPrompt", () => {
  it("renders children in the OSS build", () => {
    render(
      <CustomLoginSignupPrompt>
        <p>Don't have an account? Sign Up</p>
      </CustomLoginSignupPrompt>,
    );

    expect(
      screen.getByText("Don't have an account? Sign Up"),
    ).toBeInTheDocument();
  });
});
