import { useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useShortcutsStore } from "@/stores/shortcuts";
import isWrappedWithClass from "../../PageComponent/utils/is-wrapped-with-class";

export interface UseSidebarHotkeysParams {
  searchInputRef: React.RefObject<HTMLInputElement>;
  setOpen: (open: boolean) => void;
  isSearchFocused: boolean;
}

/**
 * Registers the sidebar's two hotkeys: the configurable "search components"
 * shortcut (focus the search input + open the sidebar) and Esc (blur while the
 * input is focused). Extracted verbatim from FlowSidebarComponent (LE-1736 W37);
 * registration order preserved.
 */
export function useSidebarHotkeys({
  searchInputRef,
  setOpen,
  isSearchFocused,
}: UseSidebarHotkeysParams): boolean {
  const [isSearchHotkeyReady, setIsSearchHotkeyReady] = useState(false);
  const searchComponentsSidebar = useShortcutsStore(
    (state) => state.searchComponentsSidebar,
  );

  useHotkeys(
    searchComponentsSidebar,
    (e: KeyboardEvent) => {
      if (isWrappedWithClass(e, "noflow")) return;
      e.preventDefault();
      searchInputRef.current?.focus();
      setOpen(true);
    },
    {
      preventDefault: true,
    },
  );

  useHotkeys(
    "esc",
    (event) => {
      event.preventDefault();
      searchInputRef.current?.blur();
    },
    {
      enableOnFormTags: true,
      enabled: isSearchFocused,
    },
  );

  // react-hotkeys-hook installs its document listener in a layout effect. This
  // passive effect runs afterwards, so consumers can distinguish a rendered
  // sidebar from one whose search shortcut is ready to receive input.
  useEffect(() => {
    setIsSearchHotkeyReady(true);
  }, [searchComponentsSidebar]);

  return isSearchHotkeyReady;
}
