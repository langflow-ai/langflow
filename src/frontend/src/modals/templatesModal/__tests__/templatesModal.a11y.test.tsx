import { act, render, screen } from "@testing-library/react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { axe } from "@/utils/a11y-test";
import TemplatesModal from "../index";

jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useParams: () => ({}),
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/utils/analytics", () => ({ track: jest.fn() }));

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => jest.fn(() => Promise.resolve("flow-id")),
}));

// Both panes import .png assets, and jest.config.js has no image
// moduleNameMapper, so importing them for real throws. They are stubbed as
// opaque panes — the surface under audit here is the modal shell plus its
// real Nav sidebar, which are kept intact.
jest.mock("../components/GetStartedComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="get-started-component">Get started</div>,
}));
jest.mock("../components/TemplateContentComponent", () => ({
  __esModule: true,
  default: () => (
    <div data-testid="template-content-component">Template list</div>
  ),
}));

// Hoisted so the selector returns a referentially stable object.
const mockUtilityState = { hideStarterProjects: false };
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (selector: (state: unknown) => unknown) =>
    selector(mockUtilityState),
}));

const example = (overrides: Record<string, unknown>) =>
  ({ id: String(overrides.name), ...overrides }) as never;

/** A populated catalog: the nav disables tabs a policy has emptied. */
const FULL_CATALOG = [
  example({
    name: "Basic Prompting",
    name_key: "basic_prompting",
    tags: ["chatbots"],
  }),
  example({
    name: "Vector Store RAG",
    name_key: "vector_store_rag",
    tags: ["rag"],
  }),
  example({ name: "Simple Agent", name_key: "simple_agent", tags: ["agents"] }),
  example({ name: "Assistant", tags: ["assistants"] }),
];

const renderModal = () => render(<TemplatesModal open setOpen={jest.fn()} />);

describe("TemplatesModal accessibility", () => {
  beforeEach(() => {
    act(() => {
      useFlowsManagerStore.setState({ examples: FULL_CATALOG });
    });
  });

  it("should_have_no_axe_violations_when_open", async () => {
    renderModal();

    // BaseModal portals its content to document.body, outside the render
    // container.
    expect(await axe(document.body)).toHaveNoViolations();
  });

  // TemplatesModal renders only BaseModal.Content — there is no
  // BaseModal.Header to supply a DialogTitle, so it names itself through
  // BaseModal's `ariaLabel`. Without it the dialog announced as the literal
  // string "Dialog" (WCAG 2.4.6 / 4.1.2).
  it("should_expose_the_dialog_with_a_meaningful_accessible_name", () => {
    renderModal();

    expect(screen.getByRole("dialog")).toHaveAccessibleName("Templates");
    expect(screen.queryByRole("dialog", { name: "Dialog" })).toBeNull();
  });

  it("should_expose_the_template_categories_as_a_navigation_list", () => {
    renderModal();

    // The category rail is the only way to move between template groups, so
    // its entries must be real, named controls (WCAG 2.1.1 / 4.1.2).
    expect(
      screen.getByRole("button", { name: /get started/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /all templates/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /assistants/i }),
    ).toBeInTheDocument();
  });

  it("should_render_the_get_started_pane_by_default", () => {
    renderModal();

    expect(screen.getByTestId("get-started-component")).toBeInTheDocument();
    expect(
      screen.queryByTestId("template-content-component"),
    ).not.toBeInTheDocument();
  });

  it("should_omit_an_emptied_category_from_the_navigation", async () => {
    // A tab a policy emptied is removed rather than left inert, so the rail
    // never offers a control that leads nowhere (WCAG 2.4.3 / 4.1.2).
    act(() => {
      useFlowsManagerStore.setState({
        examples: [example({ name: "Vector Store RAG", tags: ["rag"] })],
      });
    });

    renderModal();

    expect(screen.getByRole("button", { name: /rag/i })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /coding/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /get started/i })).toBeNull();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_expose_the_blank_flow_action_as_a_named_button", () => {
    renderModal();

    // The icon is rendered by the globally mocked genericIconComponent, so the
    // button's name has to come from its own text — which it does.
    expect(screen.getByTestId("blank-flow")).toHaveAccessibleName(
      /blank flow/i,
    );
  });

  it("should_not_nest_a_main_landmark_inside_the_dialog", () => {
    renderModal();

    // The page behind the modal already owns the single main landmark, so a
    // second one here would break landmark navigation (WCAG 2.4.1).
    expect(screen.queryByRole("main")).not.toBeInTheDocument();
    expect(screen.getByTestId("get-started-component")).toBeInTheDocument();
  });
});
