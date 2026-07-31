import { render } from "@testing-library/react";
import {
  CustomAdminPageMenuItem,
  SHOW_LEGACY_ADMIN_PAGE,
} from "../custom-admin-page-menu-item";

describe("CustomAdminPageMenuItem", () => {
  it("preserves the legacy Admin Page link in OSS", () => {
    expect(SHOW_LEGACY_ADMIN_PAGE).toBe(true);
  });

  it("does not render Enterprise navigation in OSS", () => {
    const { container } = render(
      <CustomAdminPageMenuItem onNavigate={jest.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
