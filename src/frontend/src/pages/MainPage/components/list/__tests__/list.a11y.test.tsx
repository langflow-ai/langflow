import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FlowType } from "@/types/flow";
import ListComponent from "../index";

const mockNavigate = jest.fn();

// Mock data-layer and modal dependencies — this suite only asserts the
// card's interactive semantics (a11y-action-plan 2.2).
jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: undefined }),
}));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));
jest.mock("@/hooks/flows/use-delete-flow", () => ({
  __esModule: true,
  default: () => ({ deleteFlow: jest.fn() }),
}));
jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/modals/exportModal", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/modals/flowSettingsModal", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/pages/MainPage/components/dropdown", () => ({
  __esModule: true,
  default: () => null,
}));

const flowData = {
  id: "flow-123",
  name: "My Flow",
  description: "A test flow",
  is_component: false,
  updated_at: new Date().toISOString(),
} as FlowType;

// The card resolves its icon asynchronously (getIcon().then(setIcon));
// flush that update inside the test to avoid act() warnings.
const renderCard = async ({
  selected = false,
  setSelected = jest.fn(),
  shiftPressed = false,
  flow = flowData,
}: {
  selected?: boolean;
  setSelected?: (selected: boolean) => void;
  shiftPressed?: boolean;
  flow?: FlowType;
} = {}) => {
  const view = render(
    <ListComponent
      flowData={flow}
      selected={selected}
      setSelected={setSelected}
      shiftPressed={shiftPressed}
    />,
  );
  await act(async () => {});
  return view;
};

describe("Flow list card accessibility", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_render_flow_name", async () => {
    await renderCard();

    expect(screen.getByText("My Flow")).toBeInTheDocument();
  });

  it("should_expose_primary_open_action_without_making_card_interactive", async () => {
    await renderCard();

    const card = screen.getByTestId("list-card");
    const openButton = screen.getByTestId("list-card-open-button");

    expect(card).not.toHaveAttribute("role");
    expect(card).not.toHaveAttribute("tabindex");
    expect(openButton).toHaveAccessibleName(/My Flow/);
  });

  it("should_keep_nested_controls_outside_primary_open_button", async () => {
    await renderCard();

    const openButton = screen.getByTestId("list-card-open-button");
    const checkbox = screen.getByTestId("checkbox-flow-123");
    const menuButton = screen.getByTestId("home-dropdown-menu");

    expect(openButton).not.toContainElement(checkbox);
    expect(openButton).not.toContainElement(menuButton);
    expect(openButton.querySelector("button,input,a,[role='button']")).toBe(
      null,
    );
  });

  it("should_make_primary_open_action_keyboard_focusable", async () => {
    await renderCard();

    const openButton = screen.getByTestId("list-card-open-button");
    act(() => {
      openButton.focus();
    });
    expect(openButton).toHaveFocus();
  });

  it("should_open_flow_from_primary_action", async () => {
    const user = userEvent.setup();
    await renderCard();

    await user.click(screen.getByTestId("list-card-open-button"));

    expect(mockNavigate).toHaveBeenCalledWith("/flow/flow-123");
  });

  it("should_select_flow_from_primary_action_when_shift_pressed", async () => {
    const user = userEvent.setup();
    const setSelected = jest.fn();
    await renderCard({ setSelected, shiftPressed: true });

    await user.click(screen.getByTestId("list-card-open-button"));

    expect(setSelected).toHaveBeenCalledWith(true);
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("should_not_expose_noop_open_action_for_components", async () => {
    await renderCard({
      flow: {
        ...flowData,
        id: "component-123",
        name: "My Component",
        is_component: true,
      } as FlowType,
    });

    expect(
      screen.queryByTestId("list-card-open-button"),
    ).not.toBeInTheDocument();
  });
});
