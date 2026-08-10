import type { PromptModalType } from "../../types/components";
import PromptEditorModal from "../promptEditorModal";
import { fstringStrategy } from "../promptEditorModal/strategies";

/**
 * Thin wrapper kept for existing consumers: the f-string prompt editor is
 * PromptEditorModal parameterized with the f-string syntax strategy.
 */
export default function PromptModal(props: PromptModalType): JSX.Element {
  return <PromptEditorModal {...props} strategy={fstringStrategy} />;
}
