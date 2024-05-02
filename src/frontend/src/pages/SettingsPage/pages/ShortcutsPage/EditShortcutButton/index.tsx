import { useEffect, useState } from "react";
import useAlertStore from "../../../../../stores/alertStore";

import ForwardedIconComponent from "../../../../../components/genericIconComponent";
import { Button } from "../../../../../components/ui/button";
import BaseModal from "../../../../../modals/baseModal";
import { useShortcutsStore } from "../../../../../stores/shortcuts";

export default function EditShortcutButton({
  children,
  shortcut,
  defaultShortcuts,
  defaultCombination,
  open,
  setOpen,
  disable,
}: {
  children: JSX.Element;
  shortcut: string[];
  defaultShortcuts: Array<{ name: string; shortcut: string }>;
  defaultCombination: string;
  open: boolean;
  setOpen: (bool: boolean) => void;
  disable?: boolean;
}): JSX.Element {
  const isMac = navigator.userAgent.toUpperCase().includes("MAC");
  const [key, setKey] = useState<string>(isMac ? "Meta" : "Ctrl");
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setShortcuts = useShortcutsStore((state) => state.setShortcuts);
  const unavaliableShortcuts = useShortcutsStore(
    (state) => state.unavailableShortcuts
  );
  const setErrorData = useAlertStore((state) => state.setErrorData);

  function canEditCombination(newCombination: string): boolean {
    let canSave = true;
    unavaliableShortcuts.forEach((s) => {
      if (s.toLowerCase() === newCombination.toLowerCase()) {
        canSave = false;
      }
    });
    return canSave;
  }

  const setUniqueShortcut = useShortcutsStore(
    (state) => state.updateUniqueShortcut
  );

  function editCombination(): void {
    console.log(canEditCombination(key));
    if (canEditCombination(key)) {
      const newCombination = defaultShortcuts.map((s) => {
        if (s.name === shortcut[0]) {
          return { name: s.name, shortcut: key };
        }
        return { name: s.name, shortcut: s.shortcut };
      });
      const unavailable = unavaliableShortcuts.map((s) => {
        if (s.toLowerCase() === defaultCombination.toLowerCase())
          return (s = key.toUpperCase());
        return s;
      });
      const fixCombination = key.split(" ");
      fixCombination[0] = "mod";
      const shortcutName = shortcut[0].split(" ")[0].toLowerCase();
      setUniqueShortcut(shortcutName, fixCombination.join("").toLowerCase());
      setShortcuts(newCombination, unavailable);
      setOpen(false);
      setSuccessData({ title: `${shortcut[0]} shortcut successfully changed` });
      setKey(isMac ? "META" : "CTRL");
      localStorage.setItem(
        "langflow-shortcuts",
        JSON.stringify(newCombination)
      );
      localStorage.setItem("langflow-UShortcuts", JSON.stringify(unavailable));
      return;
    }
    setErrorData({
      title: "Error saving key combination",
      list: ["This combination already exists!"],
    });
  }

  useEffect(() => {
    if (!open) setKey(isMac ? "META" : "CTRL");
    console.log(key);
  }, [open, setOpen, key]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      e.preventDefault();
      if (key.toUpperCase().includes(e.key.toUpperCase())) return;
      setKey((oldKey) => `${oldKey.toUpperCase()} + ${e.key.toUpperCase()}`);
    }

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [key, setKey]);

  return (
    <BaseModal open={open} setOpen={setOpen} size="smaller" disable={disable}>
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
        <div className="align-center flex h-full w-full justify-center gap-4">
          <div className="flex items-center justify-center text-center text-lg font-bold">
            {key.toUpperCase()}
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <Button onClick={editCombination}>Edit Combination</Button>
        <Button
          className="mr-5"
          variant={"destructive"}
          onClick={() => setKey(isMac ? "META" : "CTRL")}
        >
          Reset Combination
        </Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
