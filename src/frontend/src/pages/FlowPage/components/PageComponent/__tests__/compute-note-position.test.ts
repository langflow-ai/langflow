import {
  NOTE_NODE_MIN_HEIGHT,
  NOTE_NODE_MIN_WIDTH,
} from "@/constants/constants";
import { computeNoteScreenPosition } from "../utils/compute-note-position";

const GAP = 16;

function makeDOMRect(overrides: Partial<DOMRect> = {}): DOMRect {
  return {
    left: 0,
    top: 0,
    width: 0,
    height: 0,
    right: 0,
    bottom: 0,
    x: 0,
    y: 0,
    toJSON: () => ({}),
    ...overrides,
  } as DOMRect;
}

describe("computeNoteScreenPosition", () => {
  const originalInnerWidth = window.innerWidth;
  const originalInnerHeight = window.innerHeight;

  beforeEach(() => {
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 1200,
    });
    Object.defineProperty(window, "innerHeight", {
      writable: true,
      configurable: true,
      value: 800,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: originalInnerWidth,
    });
    Object.defineProperty(window, "innerHeight", {
      writable: true,
      configurable: true,
      value: originalInnerHeight,
    });
  });

  describe("when toolbar rect is provided", () => {
    it("should center the note horizontally on the toolbar", () => {
      const toolbarRect = makeDOMRect({ left: 400, width: 400, top: 700 });

      const pos = computeNoteScreenPosition(toolbarRect);

      // screenX = left + width/2 = 600; x = screenX - noteWidth/2
      expect(pos.x).toBe(600 - NOTE_NODE_MIN_WIDTH / 2);
    });

    it("should place the note above the toolbar with a 16px gap", () => {
      const toolbarRect = makeDOMRect({ left: 400, width: 400, top: 700 });

      const pos = computeNoteScreenPosition(toolbarRect);

      // screenY = top - noteHeight - GAP
      expect(pos.y).toBe(700 - NOTE_NODE_MIN_HEIGHT - GAP);
    });

    it("should handle a toolbar at left edge (left=0)", () => {
      const toolbarRect = makeDOMRect({ left: 0, width: 200, top: 750 });

      const pos = computeNoteScreenPosition(toolbarRect);

      expect(pos.x).toBe(100 - NOTE_NODE_MIN_WIDTH / 2);
      expect(pos.y).toBe(750 - NOTE_NODE_MIN_HEIGHT - GAP);
    });

    it("should handle a very wide toolbar spanning the full viewport", () => {
      const toolbarRect = makeDOMRect({ left: 0, width: 1200, top: 760 });

      const pos = computeNoteScreenPosition(toolbarRect);

      expect(pos.x).toBe(600 - NOTE_NODE_MIN_WIDTH / 2);
      expect(pos.y).toBe(760 - NOTE_NODE_MIN_HEIGHT - GAP);
    });
  });

  describe("when toolbar rect is null or undefined", () => {
    it("should fall back to horizontal viewport centre when rect is null", () => {
      const pos = computeNoteScreenPosition(null);

      // screenX = innerWidth/2 = 600; x = screenX - noteWidth/2
      expect(pos.x).toBe(600 - NOTE_NODE_MIN_WIDTH / 2);
    });

    it("should fall back to vertical viewport centre when rect is null", () => {
      const pos = computeNoteScreenPosition(null);

      // screenY = innerHeight/2 = 400; y = 400 (no note-height subtraction for fallback)
      expect(pos.y).toBe(400);
    });

    it("should fall back to viewport centre when rect is undefined", () => {
      const pos = computeNoteScreenPosition(undefined);

      expect(pos.x).toBe(600 - NOTE_NODE_MIN_WIDTH / 2);
      expect(pos.y).toBe(400);
    });

    it("should update fallback when viewport dimensions change", () => {
      Object.defineProperty(window, "innerWidth", { value: 800 });
      Object.defineProperty(window, "innerHeight", { value: 600 });

      const pos = computeNoteScreenPosition(null);

      expect(pos.x).toBe(400 - NOTE_NODE_MIN_WIDTH / 2);
      expect(pos.y).toBe(300);
    });
  });

  describe("output shape", () => {
    it("should always return an object with x and y number properties", () => {
      const withToolbar = computeNoteScreenPosition(
        makeDOMRect({ left: 300, width: 600, top: 720 }),
      );
      const withoutToolbar = computeNoteScreenPosition(null);

      expect(typeof withToolbar.x).toBe("number");
      expect(typeof withToolbar.y).toBe("number");
      expect(typeof withoutToolbar.x).toBe("number");
      expect(typeof withoutToolbar.y).toBe("number");
    });

    it("should not include extra properties", () => {
      const pos = computeNoteScreenPosition(null);

      expect(Object.keys(pos)).toEqual(["x", "y"]);
    });
  });
});
