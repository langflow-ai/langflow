import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import APITabsComponent from "../code-tabs";

// Prism tokenises the snippets into styled spans. A plain <pre> keeps the
// generated text queryable without the cost.
jest.mock("react-syntax-highlighter", () => ({
  __esModule: true,
  Prism: ({ children }: { children: React.ReactNode }) => <pre>{children}</pre>,
}));
jest.mock("react-syntax-highlighter/dist/cjs/styles/prism", () => ({
  __esModule: true,
  oneDark: {},
  oneLight: {},
}));

// Hoisted, referentially stable state: a fresh object per selector call
// loops the effects that key on `nodes`.
const mockFlowState = {
  nodes: [],
  currentFlow: { id: "flow-1", endpoint_name: "my-endpoint" },
  inputs: [],
  outputs: [],
};
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) => selector(mockFlowState),
}));

const mockAuthState = { isAuthenticated: true };
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) => selector(mockAuthState),
}));

const mockTweaksState = { tweaks: {} };
jest.mock("@/stores/tweaksStore", () => ({
  useTweaksStore: (selector: (state: unknown) => unknown) =>
    selector(mockTweaksState),
}));

// Every rendered snippet, joined: some tabs split the request into steps.
const snippetText = () =>
  Array.from(document.querySelectorAll("pre"), (pre) => pre.textContent).join(
    "\n",
  );

describe("APITabsComponent", () => {
  it("opens on the v2 Workflow API", () => {
    render(<APITabsComponent />);

    expect(screen.getByTestId("api_version_v2")).toHaveAttribute(
      "data-state",
      "active",
    );
    expect(snippetText()).toContain("/api/v2/workflows");
  });

  it("shows both versions without a beta badge", () => {
    render(<APITabsComponent />);

    expect(screen.getByTestId("api_version_v1")).toHaveTextContent(/^v1$/);
    expect(screen.getByTestId("api_version_v2")).toHaveTextContent(/^v2$/);
    expect(screen.queryByText(/beta/i)).not.toBeInTheDocument();
  });

  it.each([
    ["api_tab_python", "/api/v2/workflows"],
    ["api_tab_javascript", "/api/v2/workflows"],
    ["api_tab_curl", "/api/v2/workflows"],
  ])("renders the v2 snippet for %s by default", async (tabId, endpoint) => {
    const user = userEvent.setup();
    render(<APITabsComponent />);

    await user.click(screen.getByTestId(tabId));

    expect(snippetText()).toContain(endpoint);
    expect(snippetText()).toContain("flow-1");
  });

  it("still switches to the v1 run snippets", async () => {
    const user = userEvent.setup();
    render(<APITabsComponent />);

    await user.click(screen.getByTestId("api_version_v1"));

    expect(snippetText()).toContain("/api/v1/run/");
    expect(snippetText()).not.toContain("/api/v2/workflows");
  });
});
