import { render, screen } from "@testing-library/react";
import NodeUpdateComponent from "../index";

// Resolve keys against the shipped catalog so the assertions read as the copy a
// user sees, and a renamed or missing key fails here instead of shipping blank.
const copy = jest.requireActual("@/locales/en.json") as Record<string, string>;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) =>
      (jest.requireActual("@/locales/en.json") as Record<string, string>)[
        key
      ] ?? key,
  }),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    loading: _loading,
    ...props
  }: {
    children: React.ReactNode;
    loading?: boolean;
  }) => <button {...props}>{children}</button>,
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: unknown[]) => classes.filter(Boolean).join(" "),
}));

const renderBanner = (
  props: Partial<React.ComponentProps<typeof NodeUpdateComponent>> = {},
) =>
  render(
    <NodeUpdateComponent
      hasBreakingChange={false}
      showNode={true}
      handleUpdateCode={jest.fn()}
      loadingUpdate={false}
      setDismissAll={jest.fn()}
      {...props}
    />,
  );

describe("NodeUpdateComponent blocked copy", () => {
  // A missing template has two causes with the same symptom. The banner is the
  // only place the flow says which one applies.
  it("names the catalog policy when custom components are allowed", () => {
    renderBanner({ blocked: true, blockedByCatalogPolicy: true });

    expect(
      screen.getByText(copy["node.updateBlockedByPolicyLabel"]),
    ).toBeInTheDocument();
    expect(
      screen.getByText(copy["node.updateBlockedByPolicyMessage"]),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(copy["node.updateBlockedLabel"]),
    ).not.toBeInTheDocument();
  });

  it("keeps the custom-components-disabled copy in restricted mode", () => {
    renderBanner({
      blocked: true,
      blockedByCatalogPolicy: false,
      isRequired: true,
    });

    expect(
      screen.getByText(copy["node.updateBlockedLabel"]),
    ).toBeInTheDocument();
    expect(
      screen.getByTitle(copy["node.updateBlockedMessage"]),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(copy["node.updateBlockedByPolicyLabel"]),
    ).not.toBeInTheDocument();
  });

  it("shows the policy message on a dismissed required banner", () => {
    renderBanner({
      blocked: true,
      blockedByCatalogPolicy: true,
      dismissed: true,
      isRequired: true,
    });

    expect(
      screen.getByText(copy["node.updateBlockedByPolicyMessage"]),
    ).toBeInTheDocument();
  });

  it("offers no update action while blocked", () => {
    renderBanner({ blocked: true, blockedByCatalogPolicy: true });

    expect(screen.queryByTestId("update-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dismiss-warning-bar")).not.toBeInTheDocument();
  });

  it("keeps the blocked label readable on a collapsed node", () => {
    // Collapsed nodes hide the label for every other state, but a blocked node
    // has no update button, so hiding it would leave nothing to explain it.
    renderBanner({
      blocked: true,
      blockedByCatalogPolicy: true,
      showNode: false,
    });

    expect(
      screen.getByText(copy["node.updateBlockedByPolicyLabel"]),
    ).toBeInTheDocument();
    expect(
      screen.getByText(copy["node.updateBlockedByPolicyMessage"]),
    ).toHaveClass("sr-only");
  });

  it("leaves an unblocked banner untouched", () => {
    renderBanner({ blocked: false });

    expect(screen.getByText(copy["node.updateReadyLabel"])).toBeInTheDocument();
    expect(screen.getByTestId("update-button")).toBeInTheDocument();
  });
});
