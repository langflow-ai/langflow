import { render } from "@testing-library/react";
import TemplateGetStartedCardComponent from "../index";

const mockAddFlow = jest.fn(() => Promise.resolve("flow-id"));
jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => mockAddFlow,
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/utils/analytics", () => ({ track: jest.fn() }));

jest.mock("@/utils/reactflowUtils", () => ({ updateIds: jest.fn() }));

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: (selector: (state: { myCollectionId: string }) => unknown) =>
    selector({ myCollectionId: "folder-1" }),
}));

jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: "folder-1" }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true" />
  ),
}));

const baseProps = {
  bgImage: "bg.png",
  bgHorizontalImage: "bg-h.png",
  icon: "Sparkles",
  category: "Get started",
  flow: {
    name: "Basic Prompting",
    description: "A simple flow",
    data: { nodes: [], edges: [] },
  },
  loading: false,
  onFlowCreating: jest.fn(),
} as unknown as Parameters<typeof TemplateGetStartedCardComponent>[0];

describe("TemplateGetStartedCardComponent focus order", () => {
  it("should_use_tabindex_zero_so_focus_follows_document_order", () => {
    const { container } = render(
      <TemplateGetStartedCardComponent {...baseProps} />,
    );

    const card = container.firstElementChild as HTMLElement;
    expect(card).toHaveAttribute("tabindex", "0");
    expect(container.querySelectorAll("[tabindex='1']")).toHaveLength(0);
  });

  it("should_expose_the_card_as_a_button_named_after_the_flow", () => {
    const { getByRole } = render(
      <TemplateGetStartedCardComponent {...baseProps} />,
    );

    expect(
      getByRole("button", { name: "Basic Prompting" }),
    ).toBeInTheDocument();
  });
});
