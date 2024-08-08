import { useShortcutsStore } from "@/stores/shortcuts";
import { useHotkeys } from "react-hotkeys-hook";
import isWrappedWithClass from "../../PageComponent/utils/is-wrapped-with-class";

export default function useShortcuts(
    {
        showOverrideModal,
        showModalAdvanced,
        FreezeAllVertices,
        Freeze,
        downloadFunction,
        displayDocs,
        saveComponent,
        showAdvance
    }: {
        showOverrideModal: boolean,
        showModalAdvanced: boolean,
        FreezeAllVertices: () => void,
        Freeze: () => void,
        downloadFunction: () => void,
        displayDocs: () => void,
        saveComponent: () => void,
        showAdvance: () => void

    }) {
    const advanced = useShortcutsStore((state) => state.advanced);
    const minimize = useShortcutsStore((state) => state.minimize);
    const component = useShortcutsStore((state) => state.component);
    const save = useShortcutsStore((state) => state.save);
    const docs = useShortcutsStore((state) => state.docs);
    const code = useShortcutsStore((state) => state.code);
    const group = useShortcutsStore((state) => state.group);
    const download = useShortcutsStore((state) => state.download);
    const freeze = useShortcutsStore((state) => state.freeze);
    const freezeAll = useShortcutsStore((state) => state.FreezePath);

    function handleFreezeAll(e: KeyboardEvent) {
        if (isWrappedWithClass(e, "noflow")) return;
        e.preventDefault();
        FreezeAllVertices();
    }

    function handleFreeze(e: KeyboardEvent) {
        if (isWrappedWithClass(e, "noflow")) return;
        e.preventDefault();
        Freeze();
    }

    function handleDownloadWShortcut(e: KeyboardEvent) {
        e.preventDefault();
        downloadFunction();
    }

    function handleDocsWShortcut(e: KeyboardEvent) {
        e.preventDefault();
        displayDocs();
    }

    function handleSaveWShortcut(e: KeyboardEvent) {
        if (isWrappedWithClass(e, "noflow") && !showOverrideModal) return;
        e.preventDefault();
        saveComponent();
    }

    function handleAdvancedWShortcut(e: KeyboardEvent) {
        if (isWrappedWithClass(e, "noflow") && !showModalAdvanced) return;
        e.preventDefault();
        showAdvance();
      }

    useHotkeys(minimize, handleMinimizeWShortcut, { preventDefault: true });
    useHotkeys(group, handleGroupWShortcut, { preventDefault: true });
    useHotkeys(component, handleShareWShortcut, { preventDefault: true });
    useHotkeys(code, handleCodeWShortcut, { preventDefault: true });
    useHotkeys(advanced, handleAdvancedWShortcut, { preventDefault: true });
    useHotkeys(save, handleSaveWShortcut, { preventDefault: true });
    useHotkeys(docs, handleDocsWShortcut, { preventDefault: true });
    useHotkeys(download, handleDownloadWShortcut, { preventDefault: true });
    useHotkeys(freeze, handleFreeze);
    useHotkeys(freezeAll, handleFreezeAll);
}