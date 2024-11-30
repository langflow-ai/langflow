import { useShortcutsStore } from "@/stores/shortcuts";
import { useHotkeys } from "react-hotkeys-hook";
import isWrappedWithClass from "../../PageComponent/utils/is-wrapped-with-class";

export default function useShortcuts({
  showOverrideModal,
  showModalAdvanced,
  openModal,
  showconfirmShare,
  FreezeAllVertices,
  Freeze,
  downloadFunction,
  displayDocs,
  saveComponent,
  showAdvance,
  handleCodeModal,
  shareComponent,
  ungroup,
  minimizeFunction,
  activateToolMode,
  hasToolMode,
}: {
  showOverrideModal?: boolean;
  showModalAdvanced?: boolean;
  openModal?: boolean;
  showconfirmShare?: boolean;
  FreezeAllVertices?: () => void;
  Freeze?: () => void;
  downloadFunction?: () => void;
  displayDocs?: () => void;
  saveComponent?: () => void;
  showAdvance?: () => void;
  handleCodeModal?: () => void;
  shareComponent?: () => void;
  ungroup?: () => void;
  minimizeFunction?: () => void;
  activateToolMode?: () => void;
  hasToolMode?: boolean;
}) {
  const advancedSettings = useShortcutsStore((state) => state.advancedSettings);
  const minimize = useShortcutsStore((state) => state.minimize);
  const componentShare = useShortcutsStore((state) => state.componentShare);
  const save = useShortcutsStore((state) => state.saveComponent);
  const docs = useShortcutsStore((state) => state.docs);
  const code = useShortcutsStore((state) => state.code);
  const group = useShortcutsStore((state) => state.group);
  const download = useShortcutsStore((state) => state.download);
  const freeze = useShortcutsStore((state) => state.freeze);
  const freezeAll = useShortcutsStore((state) => state.freezePath);
  const toolMode = useShortcutsStore((state) => state.toolMode);

  function handleFreezeAll(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow") || !FreezeAllVertices) return;
    e.preventDefault();
    FreezeAllVertices();
  }

  function handleFreeze(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow") || !Freeze) return;
    e.preventDefault();
    Freeze();
  }

  function handleDownloadWShortcut(e: KeyboardEvent) {
    if (!downloadFunction) return;
    e.preventDefault();
    downloadFunction();
  }

  function handleDocsWShortcut(e: KeyboardEvent) {
    if (!displayDocs) return;
    e.preventDefault();
    displayDocs();
  }

  function handleSaveWShortcut(e: KeyboardEvent) {
    if (
      (isWrappedWithClass(e, "noflow") && !showOverrideModal) ||
      !saveComponent
    )
      return;
    e.preventDefault();
    saveComponent();
  }

  function handleAdvancedWShortcut(e: KeyboardEvent) {
    if ((isWrappedWithClass(e, "noflow") && !showModalAdvanced) || !showAdvance)
      return;
    e.preventDefault();
    showAdvance();
  }

  function handleCodeWShortcut(e: KeyboardEvent) {
    if ((isWrappedWithClass(e, "noflow") && !openModal) || !handleCodeModal)
      return;
    e.preventDefault();
    handleCodeModal();
  }

  function handleShareWShortcut(e: KeyboardEvent) {
    if (
      (isWrappedWithClass(e, "noflow") && !showconfirmShare) ||
      !shareComponent
    )
      return;
    e.preventDefault();
    shareComponent();
  }

  function handleGroupWShortcut(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow") || !ungroup) return;
    e.preventDefault();
    ungroup();
  }

  function handleMinimizeWShortcut(e: KeyboardEvent) {
    if (isWrappedWithClass(e, "noflow") || !minimizeFunction) return;
    e.preventDefault();
    minimizeFunction();
  }

  function handleToolModeWShortcut(e: KeyboardEvent, hasToolMode?: boolean) {
    if (!hasToolMode) return;
    if (isWrappedWithClass(e, "noflow") || !activateToolMode) return;
    e.preventDefault();
    activateToolMode();
  }

  useHotkeys(minimize, handleMinimizeWShortcut, { preventDefault: true });
  useHotkeys(group, handleGroupWShortcut, { preventDefault: true });
  useHotkeys(componentShare, handleShareWShortcut, { preventDefault: true });
  useHotkeys(code, handleCodeWShortcut, { preventDefault: true });
  useHotkeys(advancedSettings, handleAdvancedWShortcut, {
    preventDefault: true,
  });
  useHotkeys(save, handleSaveWShortcut, { preventDefault: true });
  useHotkeys(docs, handleDocsWShortcut, { preventDefault: true });
  useHotkeys(download, handleDownloadWShortcut, { preventDefault: true });
  useHotkeys(freeze, handleFreeze);
  useHotkeys(freezeAll, handleFreezeAll);
  useHotkeys(toolMode, (e) => handleToolModeWShortcut(e, hasToolMode), {
    preventDefault: true,
  });
}
