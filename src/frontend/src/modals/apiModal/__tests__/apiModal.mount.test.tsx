/**
 * Mounting the API dialog must not save the flow.
 */
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
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

const mockSaveFlow = jest.fn(() => Promise.resolve());
jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => mockSaveFlow,
}));

// Hoisted, referentially stable state — a fresh object per selector call
// loops the effects that key on `nodes`.
const mockFlowState = {
  nodes: [{ id: "ChatInput-1", data: { node: { template: {} } } }],
  currentFlow: {
    id: "flow-1",
    endpoint_name: null as string | null,
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
      <ApiModal open={false} setOpen={jest.fn()}>
        <button type="button">Open API access</button>
      </ApiModal>
    </MemoryRouter>,
  );

describe("ApiModal mounting", () => {
  beforeEach(() => mockSaveFlow.mockClear());

  // The toolbar mounts this dialog whenever it appears, for example on leaving
  // the history view. Saving there wrote whatever the current flow held, which
  // after a preview was the previewed graph.
  it("does not save a flow that has no endpoint name", () => {
    mockFlowState.currentFlow.endpoint_name = null;

    renderModal();

    expect(mockSaveFlow).not.toHaveBeenCalled();
  });

  it("does not save a flow whose endpoint name is unchanged", () => {
    mockFlowState.currentFlow.endpoint_name = "my-endpoint";

    renderModal();

    expect(mockSaveFlow).not.toHaveBeenCalled();
  });
});
