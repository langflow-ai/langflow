

//TODO IMPLEMENT FORM LOGIC

import { useEffect, useState } from "react";
import useAlertStore from "../../../../../stores/alertStore";
import { useTypesStore } from "../../../../../stores/typesStore";
import { useGlobalVariablesStore } from "../../../../../stores/globalVariables";
import { registerGlobalVariable } from "../../../../../controllers/API";
import { ResponseErrorDetailAPI } from "../../../../../types/api";
import BaseModal from "../../../../../modals/baseModal";
import { Label } from "@radix-ui/react-select";
import { Input } from "../../../../../components/ui/input";
import InputComponent from "../../../../../components/inputComponent";
import { Textarea } from "../../../../../components/ui/textarea";
import { Button } from "../../../../../components/ui/button";
import ForwardedIconComponent from "../../../../../components/genericIconComponent";
import { defaultShortcuts } from "../../../../../constants/constants";
import { useShortcutsStore } from "../../../../../stores/shortcuts";

export default function EditShortcutButton({ children, shortcut, defaultShortcuts, defaultCombination, open, setOpen, }: {children: JSX.Element; shortcut: string[]; defaultShortcuts: Array<{name: string; shortcut: string;}>; defaultCombination: string; open: boolean; setOpen: (bool: boolean) => void;}): JSX.Element {
  const setSuccessData = useAlertStore(state => state.setSuccessData)
  const setShortcuts = useShortcutsStore(state => state.setShortcuts);
  const unavaliableShortcuts = useShortcutsStore(state => state.unavailableShortcuts);
  const isMac = navigator.userAgent.toUpperCase().includes("MAC");
  const [fields, setFields] = useState<string[]>([]);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const componentFields = useTypesStore((state) => state.ComponentFields);
  const unavaliableFields =new Set(Object.keys(useGlobalVariablesStore(
    (state) => state.unavaliableFields
  )));

  const [key, setKey] = useState<string>(isMac ? "Meta" : 'Ctrl');

  function canEditCombination(newCombination: string): boolean {
    let canSave = true;
    unavaliableShortcuts.forEach((s) => {
      if (s.toLowerCase() === newCombination.toLowerCase()) {
        canSave = false
      }
    })
    return canSave;
    }

  const setUniqueShortcut = useShortcutsStore(state => state.updateUniqueShortcut);

  function editCombination(): void {
    console.log(canEditCombination(key))
    if (canEditCombination(key)) {
      const newCombination = defaultShortcuts.map((s) => {
        if (s.name === shortcut[0]) {
          return {name: s.name, shortcut: key}
        }
        return {name: s.name, shortcut: s.shortcut};
      })
      const unavailable = unavaliableShortcuts.map((s) => {
        if (s.toLowerCase() === defaultCombination.toLowerCase()) return s = key.toUpperCase();
        return s;
      })
      const fixCombination = key.split(" ")
      fixCombination[0] = "mod"
      const shortcutName = shortcut[0].split(" ")[0].toLowerCase();
      setUniqueShortcut(shortcutName, fixCombination.join("").toLowerCase())
      setShortcuts(newCombination, unavailable)
      setOpen(false)
      setSuccessData({title: `${shortcut[0]} shortcut successfully changed`})
      setKey(isMac ? "META" : 'CTRL')
      return;
    }
    setErrorData({title: "Error saving key combination", list: ["This combination already exists!"]})
  }

  useEffect(() => {
    if (!open) setKey(isMac ? "META" : 'CTRL')
  }, [open, setOpen])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      e.preventDefault()
      if (key.toUpperCase().includes(e.key.toUpperCase())) return;
      setKey(oldKey => `${oldKey.toUpperCase()} + ${e.key.toUpperCase()}`)
    }

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [key, setKey])

  return (
    <BaseModal open={open} setOpen={setOpen} size="x-small">
      <BaseModal.Header
        description={
          "Set your new key combination"
        }
      >
        <span className="pr-2"> Key Combination </span>
        <ForwardedIconComponent
          name="Keyboard"
          className="h-6 w-6 pl-1 text-primary "
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Content>
        <div className="flex h-full w-full gap-4 align-center justify-center">
          <div className="font-bold">
            {key.toUpperCase()}
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <Button onClick={editCombination}>Edit Combination</Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
