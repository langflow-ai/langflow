import type { PromptModalType } from "../../types/components";
import PromptEditorModal from "../promptEditorModal";
import { mustacheStrategy } from "../promptEditorModal/strategies";

/**
 * Thin wrapper kept for existing consumers: the mustache prompt editor is
 * PromptEditorModal parameterized with the mustache syntax strategy.
 */
export default function MustachePromptModal(
  props: PromptModalType,
): JSX.Element {
  return <PromptEditorModal {...props} strategy={mustacheStrategy} />;
}
