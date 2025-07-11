import RenderKey from "@/components/common/renderIconComponent/components/renderKey";
import { useEffect, useState } from "react";
import ForwardedIconComponent from "../../../../../components/common/genericIconComponent";
import { Button } from "../../../../../components/ui/button";
import BaseModal from "../../../../../modals/baseModal";
import useAlertStore from "../../../../../stores/alertStore";
import { useShortcutsStore } from "../../../../../stores/shortcuts";
import { toCamelCase, toTitleCase } from "../../../../../utils/utils";

export default function EditShortcutButton({
  children,
  shortcut,
  defaultShortcuts,
  open,
  setOpen,
  disable,
  setSelected,
}: {
  children: JSX.Element;
  shortcut: string[];
  defaultShortcuts: Array<{
    name: string;
    shortcut: string;
    display_name: string;
  }>;
  open: boolean;
  setOpen: (bool: boolean) => void;
  disable?: boolean;
  setSelected: (selected: string[]) => void;
}): JSX.Element {
  const shortcutInitialValue =
    defaultShortcuts.length > 0
      ? defaultShortcuts.find(
          (s) => toCamelCase(s.name) === toCamelCase(shortcut[0]),
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
        const fixCombination = key.split(" ");
        if (
          fixCombination[0].toLowerCase().includes("ctrl") ||
          fixCombination[0].toLowerCase().includes("cmd")
        ) {
          fixCombination[0] = "mod";
        }
        const newCombination = defaultShortcuts.map((s) => {
          if (s.name === shortcut[0]) {
            return {
              name: s.name,
              display_name: s.display_name,
              shortcut: fixCombination.join("").toLowerCase(),
            };
          }
          return {
            name: s.name,
            display_name: s.display_name,
            shortcut: s.shortcut,
          };
        });
        const shortcutName = toCamelCase(shortcut[0]);
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
    const _hasNewKey = false;
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
          className="h-6 w-6 pl-1 text-primary"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Content>
        <div className="align-center flex h-full w-full justify-center gap-4 rounded-md border border-border py-2">
          <div className="flex items-center justify-center gap-0.5 text-center text-lg font-bold">
            {(key ?? shortcutInitialValue ?? "").split("+").map((k, i) => (
              <RenderKey key={i} value={k} tableRender />
            ))}
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
