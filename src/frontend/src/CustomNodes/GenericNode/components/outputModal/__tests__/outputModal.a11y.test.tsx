import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";
import OutputModal from "../index";

// Lighthouse flagged two real violations on this modal:
//   1. button-name — the copy button was icon-only with no aria-label.
//   2. aria-valid-attr-value — the active TabsTrigger's aria-controls pointed
//      at a TabsContent id that never existed, because this modal drove its
//      panel content from a sibling <SwitchOutputView> instead of real
//      TabsContent elements. Fixed by pairing each TabsTrigger with a real
//      TabsContent (Radix's expected trigger/content contract), matching the
//      pattern in components/ui/__tests__/tabs.a11y.test.tsx.
//
// SwitchOutputView is mocked here — its internals (data grids, JSON views,
// text views) are unrelated to the two ARIA fixes under test and drag in
// heavy dependencies; it has no bearing on the modal's own tab/button ARIA.
jest.mock("../components/switchOutputView", () => ({
  __esModule: true,
  default: ({ type }: { type: string }) => (
    <div data-testid={`switch-output-view-${type}`}>{type} content</div>
  ),
}));

// The global jest.setup.js mock for genericIconComponent only stubs the
// default export, not the named ForwardedIconComponent OutputModal uses.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: ({ name }: { name?: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true" />
  ),
}));

const mockFlowPool = {
  "node-1": [
    {
      data: {
        outputs: { output_name: { message: "output content" } },
        logs: { output_name: { message: "log content" } },
      },
    },
  ],
};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: { flowPool: typeof mockFlowPool }) => unknown) =>
    selector({ flowPool: mockFlowPool }),
}));

const mockSetSuccessData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector: (state: { setSuccessData: typeof mockSetSuccessData }) => unknown,
  ) => selector({ setSuccessData: mockSetSuccessData }),
}));

// userEvent.setup() installs its own navigator.clipboard stub, replacing
// any predefined one — so the writeText spy must be created after setup().
const spyOnWriteText = () =>
  jest.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);

const renderModal = () =>
  render(
    <TooltipProvider>
      <OutputModal
        nodeId="node-1"
        outputName="output_name"
        disabled={false}
        open={true}
        setOpen={jest.fn()}
      >
        <button type="button">Open</button>
      </OutputModal>
    </TooltipProvider>,
  );

describe("OutputModal accessibility", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_have_no_axe_violations", async () => {
    const { container } = renderModal();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("names the icon-only copy button after the active tab's content", async () => {
    const user = userEvent.setup();
    renderModal();

    expect(screen.getByTestId("copy-output-button")).toHaveAccessibleName(
      "Copy output",
    );

    await user.click(screen.getByRole("tab", { name: "Logs" }));

    expect(screen.getByTestId("copy-output-button")).toHaveAccessibleName(
      "Copy logs",
    );
  });

  it("gives the active tab trigger a valid aria-controls reference", () => {
    renderModal();

    const outputsTab = screen.getByRole("tab", { name: "Outputs" });
    const controlsId = outputsTab.getAttribute("aria-controls");
    expect(controlsId).toBeTruthy();
    expect(document.getElementById(controlsId as string)).toBeInTheDocument();
  });

  // Regression guard: the pill-shaped tab switcher must stay visually
  // isolated (absolute/overflow-hidden) to the trigger buttons only. Content
  // was briefly nested inside that same constrained box while wiring up
  // TabsContent, which clipped the output panel instead of letting it fill
  // the modal.
  it("does not trap the tab content panel inside the switcher's constrained box", () => {
    renderModal();

    const panel = screen.getByRole("tabpanel");
    expect(panel.className).not.toMatch(/\boverflow-hidden\b/);
    expect(panel.className).not.toMatch(/\babsolute\b/);
  });

  // Regression guard: TabsList's own base class includes w-full. That was
  // previously inert (only the outer pill div's shrink-to-fit width
  // mattered), but once TabsList itself became the absolutely positioned
  // element, an unoverridden w-full stretches the switcher to the full
  // modal width instead of staying pill-sized.
  it("keeps the tab switcher pill-sized instead of stretching full width", () => {
    renderModal();

    const tablist = screen.getByRole("tablist");
    expect(tablist.className).not.toMatch(/\bw-full\b/);
  });

  // Regression guard: TabsList clips overflow, so a default outset browser
  // focus outline on TabsTrigger gets cut off and keyboard focus becomes
  // invisible. Each trigger needs its own inset focus-visible ring, which
  // renders within the trigger's box and can't be clipped by the ancestor.
  it("gives each tab trigger a visible, non-clippable focus-visible ring", () => {
    renderModal();

    for (const tab of screen.getAllByRole("tab")) {
      expect(tab.className).toMatch(/\bfocus-visible:ring-inset\b/);
      expect(tab.className).toMatch(/\bfocus-visible:ring-2\b/);
    }
  });
});

describe("OutputModal behavior parity", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("defaults to the Outputs tab content", () => {
    renderModal();

    expect(
      screen.getByTestId("switch-output-view-outputs"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("switch-output-view-logs"),
    ).not.toBeInTheDocument();
  });

  it("switches panel content when the Logs tab is selected", async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByRole("tab", { name: "Logs" }));

    expect(screen.getByTestId("switch-output-view-logs")).toBeInTheDocument();
    expect(
      screen.queryByTestId("switch-output-view-outputs"),
    ).not.toBeInTheDocument();
  });

  it("copies the active tab's content, defaulting to outputs", async () => {
    const user = userEvent.setup();
    const writeText = spyOnWriteText();
    renderModal();

    await user.click(screen.getByTestId("copy-output-button"));

    expect(writeText).toHaveBeenCalledWith("output content");
  });

  it("copies the logs content after switching to the Logs tab", async () => {
    const user = userEvent.setup();
    const writeText = spyOnWriteText();
    renderModal();

    await user.click(screen.getByRole("tab", { name: "Logs" }));
    await user.click(screen.getByTestId("copy-output-button"));

    expect(writeText).toHaveBeenCalledWith("log content");
  });
});
