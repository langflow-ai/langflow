/**
 * The toolbar's select events, one per branch of the original handleSelectChange
 * switch. Kept as a literal union so the dispatch map below is exhaustive by
 * type and the key-coverage test can assert it (LE-1736 W29).
 */
export type ToolbarActionEvent =
  | "save"
  | "freezeAll"
  | "code"
  | "show"
  | "Share"
  | "Download"
  | "SaveAll"
  | "documentation"
  | "disabled"
  | "ungroup"
  | "override"
  | "delete"
  | "update"
  | "copy"
  | "duplicate"
  | "toolMode";

export interface ToolbarActionHandlers {
  save: () => void;
  freezeAll: () => void;
  code: () => void;
  show: () => void;
  share: () => void;
  download: () => void;
  saveAll: () => void;
  documentation: () => void;
  ungroup: () => void;
  override: () => void;
  delete: () => void;
  update: () => void;
  copy: () => void;
  duplicate: () => void;
  toolMode: () => void;
}

/**
 * Maps each toolbar select event to its handler. Replaces the 16-case
 * handleSelectChange switch with a table the component looks up by event, so
 * the branch set is a single testable structure (`disabled` is an intentional
 * no-op, exactly as the original switch). Behavior-preserving (LE-1736 W29).
 */
export function buildToolbarActionMap(
  handlers: ToolbarActionHandlers,
): Record<ToolbarActionEvent, () => void> {
  return {
    save: handlers.save,
    freezeAll: handlers.freezeAll,
    code: handlers.code,
    show: handlers.show,
    Share: handlers.share,
    Download: handlers.download,
    SaveAll: handlers.saveAll,
    documentation: handlers.documentation,
    disabled: () => {},
    ungroup: handlers.ungroup,
    override: handlers.override,
    delete: handlers.delete,
    update: handlers.update,
    copy: handlers.copy,
    duplicate: handlers.duplicate,
    toolMode: handlers.toolMode,
  };
}
