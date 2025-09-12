import { act, renderHook } from "@testing-library/react";

// Mock the utils first to avoid dependency issues
jest.mock("@/utils/utils", () => ({
  toCamelCase: jest.fn((str: string) => str),
}));

// Mock constants
const mockDefaultShortcuts = [
  { name: "Test", display_name: "Test", shortcut: "t" },
];
jest.mock("../../constants/constants", () => ({
  defaultShortcuts: mockDefaultShortcuts,
}));

import { useShortcutsStore } from "../shortcuts";

const mockShortcuts = [
  {
    name: "Advanced Settings",
    display_name: "Controls",
    shortcut: "mod+shift+a",
  },
  {
    name: "Search Components Sidebar",
    display_name: "Search Components on Sidebar",
    shortcut: "/",
  },
];

describe("useShortcutsStore", () => {
  beforeEach(() => {
    localStorage.clear();

    act(() => {
      useShortcutsStore.setState({
        shortcuts: mockDefaultShortcuts,
        outputInspection: "o",
        play: "p",
        flow: "mod+shift+b",
        undo: "mod+z",
        redo: "mod+y",
        redoAlt: "mod+shift+z",
        openPlayground: "mod+k",
        advancedSettings: "mod+shift+a",
        minimize: "mod+.",
        code: "space",
        copy: "mod+c",
        duplicate: "mod+d",
        componentShare: "mod+shift+s",
        docs: "mod+shift+d",
        changesSave: "mod+s",
        saveComponent: "mod+alt+s",
        delete: "backspace",
        group: "mod+g",
        cut: "mod+x",
        paste: "mod+v",
        api: "r",
        update: "mod+u",
        download: "mod+j",
        freezePath: "mod+shift+f",
        toolMode: "mod+shift+m",
        toggleSidebar: "mod+b",
        searchComponentsSidebar: "/",
      });
    });
  });

  describe("initial state", () => {
    it("should have correct default shortcuts", () => {
      const { result } = renderHook(() => useShortcutsStore());
      expect(result.current.shortcuts).toEqual(mockDefaultShortcuts);
    });

    it("should have all predefined shortcut values", () => {
      const { result } = renderHook(() => useShortcutsStore());

      expect(result.current.outputInspection).toBe("o");
      expect(result.current.play).toBe("p");
      expect(result.current.flow).toBe("mod+shift+b");
      expect(result.current.undo).toBe("mod+z");
      expect(result.current.redo).toBe("mod+y");
      expect(result.current.openPlayground).toBe("mod+k");
      expect(result.current.copy).toBe("mod+c");
      expect(result.current.paste).toBe("mod+v");
    });
  });

  describe("setShortcuts", () => {
    it("should set new shortcuts array", () => {
      const { result } = renderHook(() => useShortcutsStore());

      act(() => {
        result.current.setShortcuts(mockShortcuts);
      });

      expect(result.current.shortcuts).toEqual(mockShortcuts);
    });

    it("should replace existing shortcuts", () => {
      const { result } = renderHook(() => useShortcutsStore());

      act(() => {
        result.current.setShortcuts(mockShortcuts);
      });
      expect(result.current.shortcuts).toEqual(mockShortcuts);

      const newShortcuts = [
        {
          name: "New Shortcut",
          display_name: "New Display",
          shortcut: "mod+n",
        },
      ];

      act(() => {
        result.current.setShortcuts(newShortcuts);
      });

      expect(result.current.shortcuts).toEqual(newShortcuts);
    });

    it("should handle empty shortcuts array", () => {
      const { result } = renderHook(() => useShortcutsStore());

      act(() => {
        result.current.setShortcuts([]);
      });

      expect(result.current.shortcuts).toEqual([]);
    });
  });

  describe("updateUniqueShortcut", () => {
    it("should update a single shortcut by name", () => {
      const { result } = renderHook(() => useShortcutsStore());

      act(() => {
        result.current.updateUniqueShortcut("play", "mod+p");
      });

      expect(result.current.play).toBe("mod+p");
    });

    it("should update multiple shortcuts", () => {
      const { result } = renderHook(() => useShortcutsStore());

      act(() => {
        result.current.updateUniqueShortcut("play", "ctrl+p");
        result.current.updateUniqueShortcut("copy", "ctrl+c");
        result.current.updateUniqueShortcut("undo", "ctrl+z");
      });

      expect(result.current.play).toBe("ctrl+p");
      expect(result.current.copy).toBe("ctrl+c");
      expect(result.current.undo).toBe("ctrl+z");
    });

    it("should handle updating non-existent shortcut fields", () => {
      const { result } = renderHook(() => useShortcutsStore());

      act(() => {
        result.current.updateUniqueShortcut("customShortcut", "mod+custom");
      });

      expect((result.current as any).customShortcut).toBe("mod+custom");
    });

    it("should not affect shortcuts array when updating individual shortcuts", () => {
      const { result } = renderHook(() => useShortcutsStore());
      const originalShortcuts = result.current.shortcuts;

      act(() => {
        result.current.updateUniqueShortcut("play", "mod+p");
      });

      expect(result.current.shortcuts).toEqual(originalShortcuts);
      expect(result.current.play).toBe("mod+p");
    });
  });

  describe("getShortcutsFromStorage", () => {
    it("should do nothing when no localStorage data exists", () => {
      const { result } = renderHook(() => useShortcutsStore());
      const originalShortcuts = result.current.shortcuts;

      act(() => {
        result.current.getShortcutsFromStorage();
      });

      expect(result.current.shortcuts).toEqual(originalShortcuts);
    });
  });

  describe("state management", () => {
    it("should handle multiple simultaneous updates", () => {
      const { result } = renderHook(() => useShortcutsStore());

      act(() => {
        result.current.updateUniqueShortcut("play", "new-play");
        result.current.updateUniqueShortcut("copy", "new-copy");
        result.current.setShortcuts(mockShortcuts);
      });

      expect(result.current.shortcuts).toEqual(mockShortcuts);
      expect(result.current.play).toBe("new-play");
      expect(result.current.copy).toBe("new-copy");
    });

    it("should maintain state consistency across multiple hook instances", () => {
      const { result: result1 } = renderHook(() => useShortcutsStore());
      const { result: result2 } = renderHook(() => useShortcutsStore());

      act(() => {
        result1.current.updateUniqueShortcut("play", "shared-play");
      });

      expect(result1.current.play).toBe("shared-play");
      expect(result2.current.play).toBe("shared-play");
    });
  });

  describe("edge cases", () => {
    it("should handle shortcuts with special characters", () => {
      const { result } = renderHook(() => useShortcutsStore());

      act(() => {
        result.current.updateUniqueShortcut("special", "mod+shift+~");
      });

      expect((result.current as any).special).toBe("mod+shift+~");
    });

    it("should handle empty string shortcuts", () => {
      const { result } = renderHook(() => useShortcutsStore());

      act(() => {
        result.current.updateUniqueShortcut("empty", "");
      });

      expect((result.current as any).empty).toBe("");
    });

    it("should handle shortcuts array with duplicate names", () => {
      const { result } = renderHook(() => useShortcutsStore());
      const duplicateShortcuts = [
        { name: "Duplicate", display_name: "First", shortcut: "mod+1" },
        { name: "Duplicate", display_name: "Second", shortcut: "mod+2" },
      ];

      act(() => {
        result.current.setShortcuts(duplicateShortcuts);
      });

      expect(result.current.shortcuts).toEqual(duplicateShortcuts);
    });
  });
});
