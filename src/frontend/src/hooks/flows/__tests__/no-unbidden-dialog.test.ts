import useFlowConflictStore from "@/stores/flowConflictStore";
import { handleBlockedSave } from "../handle-blocked-save";
import { FlowSaveBlockedError } from "../save-blocked-error";

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setErrorData: jest.fn(),
      setNoticeData: jest.fn(),
      setSuccessData: jest.fn(),
    }),
  },
}));

jest.mock("@/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
}));

/**
 * The dialog is a decision the person takes, not one taken for them.
 *
 * It used to appear on its own: a background autosave that got refused, or
 * simply leaving the page, put a modal over the canvas about changes nobody had
 * asked to review. The banner is the standing surface; clicking it is the only
 * way in.
 */
describe("the conflict dialog never opens unbidden", () => {
  const flowId = "flow-under-conflict";

  beforeEach(() => {
    useFlowConflictStore.setState({
      conflict: {
        flowId,
        author: { id: "someone", username: "someone" },
        isSelf: false,
        modifiedAt: null,
        expectedToken: "expected",
        currentToken: "current",
        theirFlow: null,
      },
      dialogOpen: false,
    });
  });

  it("stays shut when a background save is refused", () => {
    const handled = handleBlockedSave(new FlowSaveBlockedError(flowId));

    expect(handled).toBe(true);
    expect(useFlowConflictStore.getState().dialogOpen).toBe(false);
  });

  it("opens when the person asks for it", () => {
    useFlowConflictStore.getState().openDialog();

    expect(useFlowConflictStore.getState().dialogOpen).toBe(true);
  });
});
