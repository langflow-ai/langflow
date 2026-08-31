import { act, renderHook, waitFor } from "@testing-library/react";
import { useShortcutsStore } from "@/stores/shortcuts";
import { useSidebarHotkeys } from "../useSidebarHotkeys";

describe("useSidebarHotkeys", () => {
  afterEach(() => {
    document.body.replaceChildren();
  });

  it("reports readiness only when the search shortcut is dispatchable", async () => {
    useShortcutsStore.setState({ searchComponentsSidebar: "/" });
    const searchInput = document.createElement("input");
    const canvas = document.createElement("div");
    document.body.append(searchInput, canvas);
    const setOpen = jest.fn();

    const { result } = renderHook(() =>
      useSidebarHotkeys({
        searchInputRef: { current: searchInput },
        setOpen,
        isSearchFocused: false,
      }),
    );

    await waitFor(() => expect(result.current).toBe(true));

    const shortcutEvent = new KeyboardEvent("keydown", {
      key: "/",
      code: "Slash",
      bubbles: true,
      cancelable: true,
    });
    act(() => {
      canvas.dispatchEvent(shortcutEvent);
    });

    expect(searchInput).toHaveFocus();
    expect(setOpen).toHaveBeenCalledTimes(1);
    expect(setOpen).toHaveBeenCalledWith(true);
    expect(shortcutEvent.defaultPrevented).toBe(true);
  });
});
