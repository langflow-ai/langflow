import { render } from "@testing-library/react";
import CustomLoginSsoOptions from "../custom-login-sso-options";

describe("CustomLoginSsoOptions", () => {
  it("renders no content in the OSS build", () => {
    const { container } = render(<CustomLoginSsoOptions />);

    expect(container).toBeEmptyDOMElement();
  });
});
