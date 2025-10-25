import { renderHook } from "@testing-library/react";
import { act } from "react";
import { useKeyboardShortcut } from "../use-overlap-shortcuts";

describe("useKeyboardShortcut", () => {
  let mockOnShortcut: jest.Mock;

  beforeEach(() => {
    mockOnShortcut = jest.fn();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("should trigger callback when shortcut is pressed", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "ctrl+s" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "save",
      expect.any(KeyboardEvent),
    );
  });

  it("should not trigger when isEnabled is false", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "ctrl+s" },
        isEnabled: false,
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).not.toHaveBeenCalled();
  });

  it("should handle mod key on Mac (converts to meta)", () => {
    Object.defineProperty(navigator, "platform", {
      value: "MacIntel",
      writable: true,
    });

    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "mod+s" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        metaKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "save",
      expect.any(KeyboardEvent),
    );
  });

  it("should handle mod key on Windows (converts to ctrl)", () => {
    Object.defineProperty(navigator, "platform", {
      value: "Win32",
      writable: true,
    });

    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "mod+s" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "save",
      expect.any(KeyboardEvent),
    );
  });

  it("should handle multiple modifiers", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { test: "ctrl+shift+k" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "k",
        ctrlKey: true,
        shiftKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "test",
      expect.any(KeyboardEvent),
    );
  });

  it("should not trigger when extra modifiers are pressed", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "ctrl+s" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        shiftKey: true, // Extra modifier
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).not.toHaveBeenCalled();
  });

  it("should handle key mappings (backspace/delete)", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { del: "delete" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "Backspace",
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "del",
      expect.any(KeyboardEvent),
    );
  });

  it("should handle key mappings (enter/return)", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { submit: "enter" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "return",
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "submit",
      expect.any(KeyboardEvent),
    );
  });

  it("should handle key mappings (escape/esc)", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { close: "escape" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "esc",
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "close",
      expect.any(KeyboardEvent),
    );
  });

  it("should handle arrow key mappings", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { moveUp: "arrowup" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "up",
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "moveUp",
      expect.any(KeyboardEvent),
    );
  });

  it("should handle multiple shortcuts", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: {
          save: "ctrl+s",
          copy: "ctrl+c",
          paste: "ctrl+v",
        },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const saveEvent = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      window.dispatchEvent(saveEvent);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "save",
      expect.any(KeyboardEvent),
    );
    mockOnShortcut.mockClear();

    act(() => {
      const copyEvent = new KeyboardEvent("keydown", {
        key: "c",
        ctrlKey: true,
        bubbles: true,
      });
      window.dispatchEvent(copyEvent);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "copy",
      expect.any(KeyboardEvent),
    );
  });

  it("should preventDefault by default", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "ctrl+s" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      const preventDefaultSpy = jest.spyOn(event, "preventDefault");
      window.dispatchEvent(event);
      expect(preventDefaultSpy).toHaveBeenCalled();
    });
  });

  it("should not preventDefault when preventDefault is false", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "ctrl+s" },
        onShortcut: mockOnShortcut,
        preventDefault: false,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      const preventDefaultSpy = jest.spyOn(event, "preventDefault");
      window.dispatchEvent(event);
      expect(preventDefaultSpy).not.toHaveBeenCalled();
    });
  });

  it("should stopPropagation by default", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "ctrl+s" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      const stopPropagationSpy = jest.spyOn(event, "stopPropagation");
      window.dispatchEvent(event);
      expect(stopPropagationSpy).toHaveBeenCalled();
    });
  });

  it("should not stopPropagation when stopPropagation is false", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "ctrl+s" },
        onShortcut: mockOnShortcut,
        stopPropagation: false,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      const stopPropagationSpy = jest.spyOn(event, "stopPropagation");
      window.dispatchEvent(event);
      expect(stopPropagationSpy).not.toHaveBeenCalled();
    });
  });

  it("should handle case-insensitive shortcuts", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "CTRL+S" },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "S",
        ctrlKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).toHaveBeenCalledWith(
      "save",
      expect.any(KeyboardEvent),
    );
  });

  it("should clean up event listener on unmount", () => {
    const { unmount } = renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: { save: "ctrl+s" },
        onShortcut: mockOnShortcut,
      }),
    );

    unmount();

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(mockOnShortcut).not.toHaveBeenCalled();
  });

  it("should update callback without re-registering event listener", () => {
    const callback1 = jest.fn();
    const callback2 = jest.fn();

    const { rerender } = renderHook(
      ({ onShortcut }) =>
        useKeyboardShortcut({
          shortcutKeys: { save: "ctrl+s" },
          onShortcut,
        }),
      {
        initialProps: { onShortcut: callback1 },
      },
    );

    // Update callback
    rerender({ onShortcut: callback2 });

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    expect(callback1).not.toHaveBeenCalled();
    expect(callback2).toHaveBeenCalledWith("save", expect.any(KeyboardEvent));
  });

  it("should stop at first matching shortcut", () => {
    renderHook(() =>
      useKeyboardShortcut({
        shortcutKeys: {
          action1: "ctrl+s",
          action2: "ctrl+s", // Same shortcut
        },
        onShortcut: mockOnShortcut,
      }),
    );

    act(() => {
      const event = new KeyboardEvent("keydown", {
        key: "s",
        ctrlKey: true,
        bubbles: true,
      });
      window.dispatchEvent(event);
    });

    // Should only be called once for the first matching action
    expect(mockOnShortcut).toHaveBeenCalledTimes(1);
    expect(mockOnShortcut).toHaveBeenCalledWith(
      "action1",
      expect.any(KeyboardEvent),
    );
  });
});
