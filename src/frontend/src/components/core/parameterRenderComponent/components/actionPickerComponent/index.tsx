import { useContext, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { scapeJSONParse } from "@/utils/reactflowUtils";
import type { InputProps, MultiselectComponentType } from "../../types";
import { ActionPickerAddingContext } from "./addingContext";

// Mirror the backend's _action_id (human_input.py) so the branch handle name matches.
const toActionId = (label: string) =>
  label.trim().toLowerCase().replace(/ /g, "_");

const baseInputClass =
  "h-6 rounded-full border border-border bg-background px-2.5 text-sm outline-none focus:border-ring";
const inputClass = `${baseInputClass} w-32`;

export default function ActionPickerComponent({
  value,
  handleOnNewValue,
  disabled,
  nodeId,
}: InputProps<string[], MultiselectComponentType>): JSX.Element {
  const { t } = useTranslation();
  const selected = Array.isArray(value) ? value : value ? [value] : [];
  const edges = useFlowStore((state) => state.edges);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const { isAdding, stopAdding } = useContext(ActionPickerAddingContext);

  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [newDraft, setNewDraft] = useState("");

  const remove = (action: string) =>
    handleOnNewValue({ value: selected.filter((a) => a !== action) });

  const isConnected = (label: string) => {
    const handle = `branch_${toActionId(label)}`;
    return edges.some((edge) => {
      if (edge.source !== nodeId || !edge.sourceHandle) return false;
      try {
        return scapeJSONParse(edge.sourceHandle)?.name === handle;
      } catch {
        return false;
      }
    });
  };

  const isDuplicate = (name: string, exceptIndex = -1) =>
    selected.some((a, i) => i !== exceptIndex && a === name);

  const startEdit = (index: number, label: string) => {
    setEditingIndex(index);
    setDraft(label);
  };

  const cancelEdit = () => {
    setEditingIndex(null);
    setDraft("");
  };

  const commitEdit = (index: number) => {
    const next = draft.trim();
    const previous = selected[index];
    if (!next || next === previous) {
      cancelEdit();
      return;
    }
    if (isDuplicate(next, index)) {
      setErrorData({
        title: t("actionPicker.alreadyExists", { action: next }),
      });
      return;
    }
    const wasConnected = isConnected(previous);
    handleOnNewValue({
      value: selected.map((a, i) => (i === index ? next : a)),
    });
    if (wasConnected) {
      setNoticeData({
        title: t("actionPicker.renamedConnectionRemoved", { previous }),
      });
    }
    cancelEdit();
  };

  const cancelAdd = () => {
    setNewDraft("");
    stopAdding();
  };

  const commitAdd = () => {
    const next = newDraft.trim();
    if (!next) {
      cancelAdd();
      return;
    }
    if (isDuplicate(next)) {
      setErrorData({
        title: t("actionPicker.alreadyExists", { action: next }),
      });
      cancelAdd();
      return;
    }
    handleOnNewValue({ value: [...selected, next] });
    cancelAdd();
  };

  if (selected.length === 0 && !isAdding) {
    return (
      <span className="text-sm text-muted-foreground">
        {t("actionPicker.noActionsSelected")}
      </span>
    );
  }

  return (
    <div className="flex w-full flex-wrap items-center gap-1.5">
      {selected.map((action, index) =>
        editingIndex === index ? (
          <input
            key={action}
            autoFocus
            value={draft}
            disabled={disabled}
            data-testid={`action-edit-input-${action}`}
            aria-label={t("actionPicker.rename", { action })}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => commitEdit(index)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitEdit(index);
              if (e.key === "Escape") cancelEdit();
            }}
            className={inputClass}
          />
        ) : (
          <Badge
            key={action}
            variant="secondaryStatic"
            size="md"
            className="gap-1 rounded-full px-2.5 font-normal"
          >
            <button
              type="button"
              disabled={disabled}
              data-testid={`action-edit-${action}`}
              onClick={() => startEdit(index, action)}
              className="cursor-text disabled:cursor-not-allowed"
            >
              {action}
            </button>
            <button
              type="button"
              disabled={disabled}
              aria-label={t("actionPicker.remove", { action })}
              data-testid={`action-remove-${action}`}
              onClick={() => remove(action)}
              className="text-muted-foreground hover:text-foreground"
            >
              <ForwardedIconComponent name="X" className="h-3 w-3" />
            </button>
          </Badge>
        ),
      )}
      {isAdding && (
        <input
          autoFocus
          value={newDraft}
          disabled={disabled}
          placeholder={t("actionPicker.namePlaceholder")}
          // Width follows the placeholder (locale-proof) instead of a fixed w-* that truncates it.
          size={t("actionPicker.namePlaceholder").length}
          data-testid="action-add-input"
          aria-label={t("actionPicker.nameAction")}
          onChange={(e) => setNewDraft(e.target.value)}
          onBlur={commitAdd}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitAdd();
            if (e.key === "Escape") cancelAdd();
          }}
          className={baseInputClass}
        />
      )}
    </div>
  );
}
