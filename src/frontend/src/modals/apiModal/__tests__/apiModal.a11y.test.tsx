import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { axe } from "@/utils/a11y-test";
import ApiModal from "../index";

// ApiModal imports four ace-builds side-effect bundles that each begin with a
// bare `ace.define(...)` referencing a global the module never creates, so
// they throw at import time under jest. They contribute no DOM.
jest.mock("ace-builds/src-noconflict/ext-language_tools", () => ({}));
jest.mock("ace-builds/src-noconflict/mode-python", () => ({}));
jest.mock("ace-builds/src-noconflict/theme-github", () => ({}));
jest.mock("ace-builds/src-noconflict/theme-twilight", () => ({}));

// Prism tokenises the snippets into hundreds of styled spans. Rendering a
// plain <pre> keeps the code block's real semantics (which is what an audit
// cares about) without the cost.
jest.mock("react-syntax-highlighter", () => ({
  __esModule: true,
  Prism: ({ children }: { children: React.ReactNode }) => <pre>{children}</pre>,
}));
jest.mock("react-syntax-highlighter/dist/cjs/styles/prism", () => ({
  __esModule: true,
  oneDark: {},
  oneLight: {},
}));

jest.mock("nanoid", () => ({ nanoid: () => "a11y-test-id" }));

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

// Hoisted, referentially stable state — a fresh object per selector call
// loops the effects that key on `nodes`.
const mockFlowState = {
  nodes: [{ id: "ChatInput-1", data: { node: { template: {} } } }],
  currentFlow: {
    id: "flow-1",
    endpoint_name: "my-endpoint",
    name: "Support agent",
  },
  setCurrentFlow: jest.fn(),
  inputs: [],
  outputs: [],
};
jest.mock("@/stores/flowStore", () => {
  const useFlowStore = (selector: (state: unknown) => unknown) =>
    selector(mockFlowState);
  // handleSave reaches for the store imperatively.
  useFlowStore.getState = () => mockFlowState;
  return { __esModule: true, default: useFlowStore };
});

const mockFlowsManagerState = { autoSaving: true };
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector(mockFlowsManagerState),
}));

const mockAuthState = { autoLogin: true, isAuthenticated: true };
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) => selector(mockAuthState),
}));

const mockTweaksState = { initialSetup: jest.fn(), tweaks: {} };
jest.mock("@/stores/tweaksStore", () => ({
  useTweaksStore: (selector: (state: unknown) => unknown) =>
    selector(mockTweaksState),
}));

// The code-tabs pane is a large independent surface (tabs + generated
// snippets + tweaks table). It is stubbed so this file audits the ApiModal
// shell and its endpoint-name dialog; the tab primitives themselves are
// covered by components/ui/__tests__/tabs.a11y.test.tsx.
jest.mock("../codeTabs/code-tabs", () => ({
  __esModule: true,
  default: () => <div data-testid="api-code-tabs">Generated code</div>,
}));

const renderModal = () =>
  render(
    <MemoryRouter>
      <ApiModal open setOpen={jest.fn()}>
        <button type="button">Open API access</button>
      </ApiModal>
    </MemoryRouter>,
  );

describe("ApiModal accessibility", () => {
  it("should_have_no_axe_violations_when_open", async () => {
    renderModal();

    // BaseModal portals its content to document.body, outside the render
    // container.
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_expose_dialog_role_with_accessible_name", () => {
    renderModal();

    expect(
      screen.getByRole("dialog", { name: /API access/ }),
    ).toBeInTheDocument();
    // BaseModal.Header supplies a real title, so the visually-hidden "Dialog"
    // fallback must not be injected.
    expect(screen.queryByText("Dialog")).not.toBeInTheDocument();
  });

  it("should_expose_the_api_key_link_as_a_named_link", () => {
    renderModal();

    // The description points users at the API keys page; a link whose name is
    // only punctuation/whitespace would be useless out of context (WCAG 2.4.4).
    const link = screen.getByRole("link");
    expect(link).toHaveAccessibleName(/api key/i);
    expect(link).toHaveAttribute("href", "/settings/api-keys");
  });

  it("should_expose_the_endpoint_name_action_as_a_named_button", () => {
    renderModal();

    expect(screen.getByTestId("endpoint-name-button")).toHaveAccessibleName(
      /endpoint name/i,
    );
  });

  it("should_open_a_named_secondary_dialog_for_the_endpoint_name", async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByTestId("endpoint-name-button"));

    const dialogs = screen.getAllByRole("dialog");
    const endpointDialog = dialogs.find((dialog) =>
      /endpoint name/i.test(dialog.getAttribute("aria-labelledby") ?? "")
        ? true
        : dialog.textContent?.includes("Endpoint Name"),
    );
    expect(endpointDialog).toBeDefined();
    expect(screen.getByRole("textbox")).toHaveValue("my-endpoint");
  });

  it("should_have_no_axe_violations_with_the_endpoint_name_dialog_open", async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByTestId("endpoint-name-button"));

    expect(await axe(document.body)).toHaveNoViolations();
  });
});
