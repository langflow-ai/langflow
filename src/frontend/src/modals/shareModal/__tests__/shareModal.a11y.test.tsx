import { render, screen } from "@testing-library/react";
import type { FlowType } from "@/types/flow";
import { axe } from "@/utils/a11y-test";
import ShareModal from "../index";

// The controllers/API barrel pulls in axios and the request interceptor at
// import time; none of it is needed to audit the dialog markup.
jest.mock("@/controllers/API", () => ({
  getStoreComponents: jest.fn().mockResolvedValue({ results: [] }),
  saveFlowStore: jest.fn().mockResolvedValue({}),
  updateFlowStore: jest.fn().mockResolvedValue({}),
}));

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

const mockAlertState = {
  setSuccessData: jest.fn(),
  setErrorData: jest.fn(),
};
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) => selector(mockAlertState),
}));

// Store state objects are hoisted so their identity stays stable across
// renders — a fresh object per selector call loops effects keyed on them.
const mockStoreState = { hasStore: false, hasApiKey: false };
jest.mock("@/stores/storeStore", () => ({
  useStoreStore: (selector: (state: unknown) => unknown) =>
    selector(mockStoreState),
}));

const mockUtilityState = { tags: [] as unknown[] };
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (selector: (state: unknown) => unknown) =>
    selector(mockUtilityState),
}));

const component = {
  id: "component-1",
  name: "Summarizer",
  description: "Summarizes long documents.",
  data: null,
  is_component: true,
} as unknown as FlowType;

// `is_component` keeps the nested ExportModal (a second dialog) out of the
// tree, so the audit stays scoped to this modal.
const renderModal = () =>
  render(
    <ShareModal open setOpen={jest.fn()} is_component component={component} />,
  );

describe("ShareModal accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    renderModal();

    // BaseModal portals its content to document.body, outside the render
    // container.
    const results = await axe(document.body);

    expect(results.violations).toEqual([]);
  });

  it("should_not_render_a_lock_switch_it_cannot_operate", () => {
    renderModal();

    // ShareModal passes no `setLocked`, so EditFlowSettings must omit the
    // switch rather than ship a focusable, unnamed, inert control.
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByTestId("lock-flow-switch")).not.toBeInTheDocument();
  });

  it("should_expose_dialog_role_with_accessible_name", () => {
    renderModal();

    expect(screen.getByRole("dialog", { name: /Share/ })).toBeInTheDocument();
    // BaseModal.Header supplies a real title, so the visually-hidden "Dialog"
    // fallback must not be injected.
    expect(screen.queryByText("Dialog")).not.toBeInTheDocument();
  });

  it("should_describe_the_dialog_from_the_header_description", () => {
    renderModal();

    expect(screen.getByRole("dialog")).toHaveAccessibleDescription(
      expect.anything() as unknown as string,
    );
  });

  it("should_associate_the_public_checkbox_with_its_label", () => {
    renderModal();

    const checkbox = screen.getByTestId("public-checkbox");
    // The label is wired with htmlFor="public"; losing that leaves the only
    // privacy control on this dialog unnamed (WCAG 1.3.1 / 4.1.2).
    expect(checkbox).toHaveAccessibleName(/public/i);
    expect(checkbox).toHaveAttribute("id", "public");
  });

  it("should_render_the_flow_name_and_description_as_static_text", () => {
    renderModal();

    // ShareModal passes no setters to EditFlowSettings, so the fields must be
    // read-only text rather than focusable inputs the user cannot actually
    // edit (WCAG 3.2.2).
    expect(screen.getByText("Summarizer")).toBeInTheDocument();
    expect(screen.getByText("Summarizes long documents.")).toBeInTheDocument();
    expect(screen.queryByTestId("input-flow-name")).not.toBeInTheDocument();
  });

  it("should_expose_the_submit_and_export_actions_as_named_buttons", () => {
    renderModal();

    expect(screen.getByTestId("share-modal-button-flow")).toHaveAccessibleName(
      /share/i,
    );
    expect(screen.getByRole("button", { name: /export/i })).toBeInTheDocument();
  });
});
