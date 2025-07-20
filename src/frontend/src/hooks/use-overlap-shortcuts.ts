import { useCallback, useEffect, useRef } from "react";

const KEY_MAPPINGS: { [key: string]: string[] } = {
  backspace: ["backspace", "delete"],
  delete: ["delete", "backspace"],
  enter: ["enter", "return"],
  escape: ["escape", "esc"],
  space: [" ", "spacebar", "space"],
  arrowup: ["arrowup", "up"],
  arrowdown: ["arrowdown", "down"],
  arrowleft: ["arrowleft", "left"],
  arrowright: ["arrowright", "right"],
};

interface UseKeyboardShortcutProps {
  shortcutKeys: { [key: string]: string };
  isEnabled?: boolean;
  onShortcut: (shortcutName: string, event: KeyboardEvent) => void;
  preventDefault?: boolean;
  stopPropagation?: boolean;
}

export const useKeyboardShortcut = ({
  shortcutKeys,
  isEnabled = true,
  onShortcut,
  preventDefault = true,
  stopPropagation = true,
}: UseKeyboardShortcutProps) => {
  const propsRef = useRef({ shortcutKeys, isEnabled, onShortcut });

  useEffect(() => {
    propsRef.current = { shortcutKeys, isEnabled, onShortcut };
  }, [shortcutKeys, isEnabled, onShortcut]);

  const normalizeKey = useCallback((key: string): string[] => {
    const lowercaseKey = key.toLowerCase();
    return KEY_MAPPINGS[lowercaseKey] || [lowercaseKey];
  }, []);

  const parseShortcut = useCallback((shortcut: string) => {
    const parts = shortcut
      .toLowerCase()
      .split("+")
      .map((part) => part.trim());

    // Handle 'mod' key (cmd on Mac, ctrl on others)
    const modIndex = parts.indexOf("mod");
    if (modIndex !== -1) {
      parts[modIndex] = navigator.platform.toLowerCase().includes("mac")
        ? "meta"
        : "ctrl";
    }

    return parts;
  }, []);

  const matchesShortcut = useCallback(
    (event: KeyboardEvent, shortcut: string) => {
      if (!shortcut) return false;

      const parts = parseShortcut(shortcut);
      const shortcutKey = parts[parts.length - 1];
      const possibleKeys = normalizeKey(shortcutKey);
      const eventKey = event.key.toLowerCase();

      // Check if the pressed key matches any possible variations
      const keyMatches = possibleKeys.includes(eventKey);

      // Get modifiers state
      const modifiers = {
        ctrl: event.ctrlKey,
        alt: event.altKey,
        shift: event.shiftKey,
        meta: event.metaKey,
      };

      // Check modifiers
      const modifierParts = parts.slice(0, -1);
      const modifiersMatch = modifierParts.every(
        (mod) => modifiers[mod as keyof typeof modifiers],
      );

      // Check no extra modifiers
      const hasExtraModifiers = Object.entries(modifiers).some(
        ([mod, pressed]) => pressed && !modifierParts.includes(mod),
      );

      return keyMatches && modifiersMatch && !hasExtraModifiers;
    },
    [normalizeKey, parseShortcut],
  );

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const { shortcutKeys, isEnabled, onShortcut } = propsRef.current;

      if (!isEnabled) return;

      for (const [name, shortcut] of Object.entries(shortcutKeys)) {
        if (matchesShortcut(event, shortcut)) {
          if (preventDefault) {
            event.preventDefault();
          }
          if (stopPropagation) {
            event.stopPropagation();
          }
          onShortcut(name, event);
          break;
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown, true);

    return () => {
      window.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [preventDefault, stopPropagation, matchesShortcut]);
};
