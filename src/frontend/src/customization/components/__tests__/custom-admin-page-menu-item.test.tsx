import { render } from "@testing-library/react";
import { CustomAdminPageMenuItem } from "../custom-admin-page-menu-item";

describe("CustomAdminPageMenuItem", () => {
  it("does not render Enterprise navigation in OSS", () => {
    const { container } = render(
      <CustomAdminPageMenuItem onNavigate={jest.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
