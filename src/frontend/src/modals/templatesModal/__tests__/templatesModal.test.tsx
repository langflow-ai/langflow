import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { useUtilityStore } from "@/stores/utilityStore";
import TemplatesModal from "../index";

const navProps: Array<Record<string, unknown>> = [];

jest.mock("react-router-dom", () => ({
  useParams: () => ({}),
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/utils/analytics", () => ({
  track: jest.fn(),
}));

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => jest.fn(() => Promise.resolve("flow-id")),
}));

jest.mock("../../baseModal", () => {
  const BaseModal = Object.assign(
    ({ children }: { children: ReactNode }) => <>{children}</>,
    {
      Content: ({ children }: { children: ReactNode }) => <>{children}</>,
      Footer: ({ children }: { children: ReactNode }) => <>{children}</>,
    },
  );

  return {
    __esModule: true,
    default: BaseModal,
  };
});

jest.mock("../components/navComponent", () => ({
  Nav: (props: Record<string, unknown>) => {
    navProps.push(props);
    return <div data-testid="templates-nav" />;
  },
}));

jest.mock("../components/GetStartedComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="get-started-component" />,
}));

jest.mock("../components/TemplateContentComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="template-content-component" />,
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

describe("TemplatesModal", () => {
  beforeEach(() => {
    navProps.length = 0;
    act(() => {
      useUtilityStore.setState({ hideStarterProjects: false });
    });
  });

  afterEach(() => {
    act(() => {
      useUtilityStore.setState({ hideStarterProjects: false });
    });
  });

  it("passes the effective tab to the nav when starter projects are hidden", () => {
    act(() => {
      useUtilityStore.setState({ hideStarterProjects: true });
    });

    render(<TemplatesModal open setOpen={jest.fn()} />);

    expect(screen.getByTestId("templates-nav")).toBeInTheDocument();
    expect(navProps.at(-1)?.currentTab).toBe("all-templates");

    const categories = navProps.at(-1)?.categories as
      | Array<{ items: Array<{ id: string }> }>
      | undefined;

    const categoryItemIds =
      categories?.flatMap((category) =>
        category.items.map((item) => item.id),
      ) ?? [];

    expect(categoryItemIds).not.toContain("get-started");
  });

  it("keeps get-started selected in the nav when starter projects are visible", () => {
    render(<TemplatesModal open setOpen={jest.fn()} />);

    expect(screen.getByTestId("templates-nav")).toBeInTheDocument();
    expect(navProps.at(-1)?.currentTab).toBe("get-started");
  });
});
