import { act, render, screen } from "@testing-library/react";
import type { FlowType } from "@/types/flow";
import ListComponent from "../index";

// Mock data-layer and modal dependencies — this suite only asserts the
// card's interactive semantics (a11y-action-plan 2.2).
jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: undefined }),
}));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
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
const renderCard = async () => {
  const view = render(
    <ListComponent
      flowData={flowData}
      selected={false}
      setSelected={() => {}}
      shiftPressed={false}
    />,
  );
  await act(async () => {});
  return view;
};

describe("Flow list card accessibility", () => {
  it("should_render_flow_name", async () => {
    await renderCard();

    expect(screen.getByText("My Flow")).toBeInTheDocument();
  });

  // Known gap (a11y-action-plan 2.2): the card is a click-only container —
  // no link or button role for the primary "open flow" action and no
  // keyboard focusability. Fails until the fix lands.
  it("should_expose_card_as_focusable_interactive_element", async () => {
    await renderCard();

    const card = screen.getByTestId("list-card");
    const role = card.getAttribute("role");
    const isNativeInteractive = ["a", "button"].includes(
      card.tagName.toLowerCase(),
    );
    expect(isNativeInteractive || role === "button" || role === "link").toBe(
      true,
    );
  });

  it("should_make_card_keyboard_focusable", async () => {
    await renderCard();

    const card = screen.getByTestId("list-card");
    act(() => {
      card.focus();
    });
    expect(card).toHaveFocus();
  });
});
