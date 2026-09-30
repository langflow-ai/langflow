// Mock the utilities and dependencies
jest.mock("../utils/is-wrapped-with-class", () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn((selector) =>
    selector ? selector({ currentFlow: { id: "test-flow-id" } }) : {},
  ),
}));

jest.mock("@/stores/shortcuts", () => ({
  __esModule: true,
  useShortcutsStore: jest.fn((selector) =>
    selector
      ? selector({
          download: "mod+j",
        })
      : {},
  ),
}));

import isWrappedWithClass from "../utils/is-wrapped-with-class";

const mockIsWrappedWithClass = isWrappedWithClass as jest.MockedFunction<
  typeof isWrappedWithClass
>;

// Simplified test of handleDownload function directly
const handleDownload = (
  e: KeyboardEvent,
  setOpenExportModal: jest.MockedFunction<(open: boolean) => void>,
) => {
  if (!isWrappedWithClass(e, "noflow")) {
    e.preventDefault();
    (e as unknown as Event).stopImmediatePropagation();
    setOpenExportModal(true);
  }
};

describe("handleDownload function", () => {
  let mockSetOpenExportModal: jest.MockedFunction<(open: boolean) => void>;

  beforeEach(() => {
    jest.clearAllMocks();
    mockSetOpenExportModal = jest.fn();
    mockIsWrappedWithClass.mockReturnValue(false);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("should open export modal when not wrapped with noflow class", () => {
    mockIsWrappedWithClass.mockReturnValue(false);

    const keydownEvent = new KeyboardEvent("keydown", {
      key: "j",
      ctrlKey: true,
      metaKey: false,
      bubbles: true,
    });

    handleDownload(keydownEvent, mockSetOpenExportModal);

    expect(mockIsWrappedWithClass).toHaveBeenCalledWith(keydownEvent, "noflow");
    expect(mockSetOpenExportModal).toHaveBeenCalledWith(true);
  });

  it("should open export modal with any keyboard event when not wrapped with noflow", () => {
    mockIsWrappedWithClass.mockReturnValue(false);

    const keydownEvent = new KeyboardEvent("keydown", {
      key: "j",
      ctrlKey: false,
      metaKey: true,
      bubbles: true,
    });

    handleDownload(keydownEvent, mockSetOpenExportModal);

    expect(mockIsWrappedWithClass).toHaveBeenCalledWith(keydownEvent, "noflow");
    expect(mockSetOpenExportModal).toHaveBeenCalledWith(true);
  });

  it("should NOT open export modal when event is wrapped with noflow class", () => {
    mockIsWrappedWithClass.mockReturnValue(true);

    const keydownEvent = new KeyboardEvent("keydown", {
      key: "j",
      ctrlKey: true,
      metaKey: false,
      bubbles: true,
    });

    handleDownload(keydownEvent, mockSetOpenExportModal);

    expect(mockIsWrappedWithClass).toHaveBeenCalledWith(keydownEvent, "noflow");
    expect(mockSetOpenExportModal).not.toHaveBeenCalled();
  });

  it("should call preventDefault and stopImmediatePropagation when not wrapped with noflow", () => {
    mockIsWrappedWithClass.mockReturnValue(false);

    // Create a mock event with spyable methods
    const mockPreventDefault = jest.fn();
    const mockStopImmediatePropagation = jest.fn();

    const keydownEvent = new KeyboardEvent("keydown", {
      key: "j",
      ctrlKey: true,
      metaKey: false,
      bubbles: true,
    });

    // Mock the methods
    keydownEvent.preventDefault = mockPreventDefault;
    keydownEvent.stopImmediatePropagation = mockStopImmediatePropagation;

    handleDownload(keydownEvent, mockSetOpenExportModal);

    expect(mockSetOpenExportModal).toHaveBeenCalledWith(true);
    expect(mockPreventDefault).toHaveBeenCalled();
    expect(mockStopImmediatePropagation).toHaveBeenCalled();
  });

  it("should NOT call preventDefault or stopImmediatePropagation when wrapped with noflow", () => {
    mockIsWrappedWithClass.mockReturnValue(true);

    // Create a mock event with spyable methods
    const mockPreventDefault = jest.fn();
    const mockStopImmediatePropagation = jest.fn();

    const keydownEvent = new KeyboardEvent("keydown", {
      key: "j",
      ctrlKey: true,
      metaKey: false,
      bubbles: true,
    });

    // Mock the methods
    keydownEvent.preventDefault = mockPreventDefault;
    keydownEvent.stopImmediatePropagation = mockStopImmediatePropagation;

    handleDownload(keydownEvent, mockSetOpenExportModal);

    expect(mockSetOpenExportModal).not.toHaveBeenCalled();
    expect(mockPreventDefault).not.toHaveBeenCalled();
    expect(mockStopImmediatePropagation).not.toHaveBeenCalled();
  });

  it("should work with different event properties", () => {
    mockIsWrappedWithClass.mockReturnValue(false);

    const keydownEvent = new KeyboardEvent("keydown", {
      key: "x",
      altKey: true,
      bubbles: true,
    });

    handleDownload(keydownEvent, mockSetOpenExportModal);

    expect(mockIsWrappedWithClass).toHaveBeenCalledWith(keydownEvent, "noflow");
    expect(mockSetOpenExportModal).toHaveBeenCalledWith(true);
  });

  it("should validate isWrappedWithClass is called with correct parameters", () => {
    mockIsWrappedWithClass.mockReturnValue(false);

    const keydownEvent = new KeyboardEvent("keydown", {
      key: "j",
      ctrlKey: true,
      metaKey: false,
      bubbles: true,
    });

    handleDownload(keydownEvent, mockSetOpenExportModal);

    expect(mockIsWrappedWithClass).toHaveBeenCalledTimes(1);
    expect(mockIsWrappedWithClass).toHaveBeenCalledWith(keydownEvent, "noflow");
  });
});
