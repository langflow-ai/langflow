import { useEffect, useState } from "react";
import useAlertStore from "../../../../../stores/alertStore";

import ForwardedIconComponent from "../../../../../components/genericIconComponent";
import { Button } from "../../../../../components/ui/button";
import BaseModal from "../../../../../modals/baseModal";
import { useShortcutsStore } from "../../../../../stores/shortcuts";
import { toTitleCase } from "../../../../../utils/utils";

export default function EditShortcutButton({
  children,
  shortcut,
  defaultShortcuts,
  defaultCombination,
  open,
  setOpen,
  disable,
  setSelected,
}: {
  children: JSX.Element;
  shortcut: string[];
  defaultShortcuts: Array<{ name: string; shortcut: string }>;
  defaultCombination: string;
  open: boolean;
  setOpen: (bool: boolean) => void;
  disable?: boolean;
  setSelected: (selected: string[]) => void;
}): JSX.Element {
  let shortcutInitialValue =
    defaultShortcuts.length > 0
      ? defaultShortcuts.find(
          (s) =>
            s.name.split(" ")[0].toLowerCase().toLowerCase() ===
            shortcut[0]?.split(" ")[0].toLowerCase(),
        )?.shortcut
      : "";
  const [key, setKey] = useState<string | null>(null);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setShortcuts = useShortcutsStore((state) => state.setShortcuts);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  function canEditCombination(newCombination: string): boolean {
    let canSave = true;
    defaultShortcuts.forEach(({ shortcut }) => {
      if (shortcut.toLowerCase() === newCombination.toLowerCase()) {
        canSave = false;
      }
    });
    return canSave;
  }

  const setUniqueShortcut = useShortcutsStore(
    (state) => state.updateUniqueShortcut,
  );

  function editCombination(): void {
    if (key) {
      if (canEditCombination(key)) {
        const newCombination = defaultShortcuts.map((s) => {
          if (s.name === shortcut[0]) {
            return { name: s.name, shortcut: key };
          }
          return { name: s.name, shortcut: s.shortcut };
        });
        const fixCombination = key.split(" ");
        if (
          fixCombination[0].toLowerCase().includes("ctrl") ||
          fixCombination[0].toLowerCase().includes("cmd")
        ) {
          fixCombination[0] = "mod";
        }
        const shortcutName = shortcut[0].split(" ")[0].toLowerCase();
        setUniqueShortcut(shortcutName, fixCombination.join("").toLowerCase());
        setShortcuts(newCombination);
        localStorage.setItem(
          "langflow-shortcuts",
          JSON.stringify(newCombination),
        );
        setKey(null);
        setOpen(false);
        setSuccessData({
          title: `${shortcut[0]} shortcut successfully changed`,
        });
        return;
      }
    }
    setErrorData({
      title: "Error saving key combination",
      list: ["This combination already exists!"],
    });
  }

  useEffect(() => {
    if (!open) {
      setKey(null);
      setSelected([]);
    }
  }, [open, setOpen, key]);

  function getFixedCombination({
    oldKey,
    key,
  }: {
    oldKey: string;
    key: string;
  }): string {
    if (oldKey === null) {
      return `${key.length > 0 ? toTitleCase(key) : toTitleCase(key)}`;
    }
    return `${
      oldKey.length > 0 ? toTitleCase(oldKey) : oldKey.toUpperCase()
    } + ${key.length > 0 ? toTitleCase(key) : key.toUpperCase()}`;
  }

  function checkForKeys(keys: string, keyToCompare: string): boolean {
    const keysArr = keys.split(" ");
    let hasNewKey = false;
    return keysArr.some(
      (k) => k.toLowerCase().trim() === keyToCompare.toLowerCase().trim(),
    );
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      e.preventDefault();
      let fixedKey = e.key;
      if (e.key?.toLowerCase() === "control") {
        fixedKey = "Ctrl";
      }
      if (e.key?.toLowerCase() === "meta") {
        fixedKey = "Cmd";
      }
      if (e.key?.toLowerCase() === " ") {
        fixedKey = "Space";
      }
      if (key) {
        if (checkForKeys(key, fixedKey)) return;
      }
      setKey((oldKey) =>
        getFixedCombination({ oldKey: oldKey!, key: fixedKey }),
      );
    }

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [key, setKey]);

  return (
    <BaseModal open={open} setOpen={setOpen} size="x-small" disable={disable}>
      <BaseModal.Header description={"Recording your keyboard"}>
        <span className="pr-2"> Key Combination </span>
        <ForwardedIconComponent
          name="Keyboard"
          className="h-6 w-6 pl-1 text-primary "
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Content>
        <div className="align-center flex h-full w-full justify-center gap-4 rounded-md border border-border py-2">
          <div className="flex items-center justify-center text-center text-lg font-bold">
            {key === null
              ? shortcutInitialValue?.toUpperCase()
              : key.toUpperCase()}
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <Button variant={"default"} onClick={editCombination}>
          Apply
        </Button>
        <Button
          className="mr-5"
          variant={"destructive"}
          onClick={() => setKey(null)}
        >
          Reset
        </Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
