import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  SimpleSidebar,
  SimpleSidebarContent,
  SimpleSidebarHeader,
  SimpleSidebarProvider,
  useSimpleSidebar,
} from "@/components/ui/simple-sidebar";
import {
  useDeleteTextAnnotationTask,
  useGetTextAnnotationProject,
  usePatchTextAnnotationProject,
  usePostTextAnnotationTasks,
  usePutTextTaskAnnotations,
} from "@/controllers/API/queries/text-annotation";
import CustomLoader from "@/customization/components/custom-loader";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import type {
  TextAnnotationLabel,
  TextAnnotationTaskItemType,
} from "@/types/text-annotation";
import { Button } from "../../components/ui/button";
import ConfirmationModal from "../../modals/confirmationModal";
import ExportAnnotationsModal from "./ExportAnnotationsModal";
import ImportCsvModal from "./ImportCsvModal";
import ImportDatabaseModal from "./ImportDatabaseModal";
import { LabelColorPicker } from "./LabelColorPicker";
import {
  categoriesToRegions,
  computeProgress,
  genSpanId,
  LABEL_COLORS,
  regionsToCategories,
  regionsToSpans,
  spansToRegions,
  type TextSpan,
} from "./types";

function colorForLabel(
  label: string,
  labels: string[],
  labelColors: Record<string, string>,
): string {
  if (labelColors[label]) return labelColors[label];
  const idx = labels.indexOf(label);
  if (idx === -1) return LABEL_COLORS[0] ?? "#ef4444";
  return LABEL_COLORS[idx % LABEL_COLORS.length] ?? "#ef4444";
}

type Segment = {
  start: number;
  end: number;
  text: string;
  spans: TextSpan[];
};

function buildSegments(text: string, spans: TextSpan[]): Segment[] {
  const points = new Set<number>();
  points.add(0);
  points.add(text.length);
  spans.forEach((s) => {
    points.add(Math.max(0, Math.min(text.length, s.start)));
    points.add(Math.max(0, Math.min(text.length, s.end)));
  });
  const sorted = Array.from(points)
    .filter((p) => p >= 0 && p <= text.length)
    .sort((a, b) => a - b);
  const segments: Segment[] = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    const start = sorted[i];
    const end = sorted[i + 1];
    if (start >= end) continue;
    segments.push({
      start,
      end,
      text: text.slice(start, end),
      spans: spans.filter((s) => s.start <= start && s.end >= end),
    });
  }
  return segments;
}

function computeGlobalOffset(
  container: HTMLElement,
  targetNode: Node,
  targetOffset: number,
): number | null {
  let offset = 0;
  let found = false;
  function walk(node: Node): boolean {
    if (found) return true;
    if (node === targetNode) {
      if (node.nodeType === Node.TEXT_NODE) {
        offset += Math.min(targetOffset, node.textContent?.length ?? 0);
      }
      found = true;
      return true;
    }
    if (node.nodeType === Node.TEXT_NODE) {
      offset += node.textContent?.length ?? 0;
      return false;
    }
    if (node.nodeType === Node.ELEMENT_NODE) {
      for (let i = 0; i < node.childNodes.length; i++) {
        if (walk(node.childNodes[i])) return true;
      }
    }
    return false;
  }
  walk(container);
  return found ? offset : null;
}

function getSelectionOffsets(
  container: HTMLElement,
): { start: number; end: number; text: string } | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return null;
  const range = sel.getRangeAt(0);
  if (!container.contains(range.commonAncestorContainer)) return null;
  const startOff = computeGlobalOffset(
    container,
    range.startContainer,
    range.startOffset,
  );
  const endOff = computeGlobalOffset(
    container,
    range.endContainer,
    range.endOffset,
  );
  if (startOff === null || endOff === null) return null;
  const start = Math.min(startOff, endOff);
  const end = Math.max(startOff, endOff);
  if (end - start < 1) return null;
  return { start, end, text: sel.toString() };
}

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsText(file);
  });
}

/** Per-task editor draft: local, unsaved span/category edits. */
interface TaskDraft {
  spans: TextSpan[];
  categories: string[];
}

function draftFromTask(task: TextAnnotationTaskItemType): TaskDraft {
  return {
    spans: regionsToSpans(task.result ?? []),
    categories: regionsToCategories(task.result ?? []),
  };
}

export default function AnnotationEditor({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const {
    data: project,
    isLoading,
    isError,
  } = useGetTextAnnotationProject({ projectId });
  const { mutate: putAnnotations, isPending: isSaving } =
    usePutTextTaskAnnotations({});
  const { mutate: postTasks } = usePostTextAnnotationTasks({});
  const { mutate: deleteTask } = useDeleteTextAnnotationTask({});
  const { mutate: patchProject } = usePatchTextAnnotationProject({});

  const [drafts, setDrafts] = useState<Record<string, TaskDraft>>({});
  const [dirtyTasks, setDirtyTasks] = useState<Record<string, boolean>>({});
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeLabel, setActiveLabel] = useState<string>("");
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const [importText, setImportText] = useState("");
  const [taskToDelete, setTaskToDelete] =
    useState<TextAnnotationTaskItemType | null>(null);

  const textContainerRef = useRef<HTMLDivElement | null>(null);

  const tasks = useMemo(() => project?.tasks ?? [], [project]);

  const entityLabelNames = useMemo(
    () => (project?.entity_labels ?? []).map((label) => label.value),
    [project],
  );
  const categoryLabelNames = useMemo(
    () => (project?.category_labels ?? []).map((label) => label.value),
    [project],
  );
  const labelColors = useMemo(() => {
    const colors: Record<string, string> = {};
    for (const label of project?.entity_labels ?? []) {
      if (label.background) colors[label.value] = label.background;
    }
    return colors;
  }, [project]);

  // Initialize selection when the project first loads / switches.
  useEffect(() => {
    if (!project) return;
    setDrafts({});
    setDirtyTasks({});
    setActiveTaskId((current) =>
      current && project.tasks.some((task) => task.id === current)
        ? current
        : (project.tasks[0]?.id ?? null),
    );
    setActiveLabel((current) =>
      current && project.entity_labels.some((label) => label.value === current)
        ? current
        : (project.entity_labels[0]?.value ?? ""),
    );
    setSelectedSpanId(null);
  }, [project?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeTask = useMemo(
    () => tasks.find((task) => task.id === activeTaskId) ?? null,
    [tasks, activeTaskId],
  );

  const activeIndex = useMemo(() => {
    if (!activeTask) return -1;
    return tasks.findIndex((task) => task.id === activeTask.id);
  }, [tasks, activeTask]);

  const getDraft = useCallback(
    (task: TextAnnotationTaskItemType): TaskDraft =>
      drafts[task.id] ?? draftFromTask(task),
    [drafts],
  );

  const activeDraft: TaskDraft = useMemo(
    () => (activeTask ? getDraft(activeTask) : { spans: [], categories: [] }),
    [activeTask, getDraft],
  );

  const progress = useMemo(
    () =>
      project
        ? computeProgress(
            tasks.map((task) => ({
              ...task,
              is_labeled: dirtyTasks[task.id]
                ? (drafts[task.id]?.spans.length ?? 0) > 0 ||
                  (drafts[task.id]?.categories.length ?? 0) > 0
                : task.is_labeled,
            })),
          )
        : { done: 0, total: 0 },
    [project, tasks, drafts, dirtyTasks],
  );

  const updateDraft = useCallback(
    (taskId: string, updater: (draft: TaskDraft) => TaskDraft) => {
      setDrafts((prev) => {
        const base =
          prev[taskId] ??
          draftFromTask(tasks.find((task) => task.id === taskId)!);
        return { ...prev, [taskId]: updater(base) };
      });
      setDirtyTasks((prev) => ({ ...prev, [taskId]: true }));
    },
    [tasks],
  );

  // ----------------------------------------------------------------------- //
  // Import handlers
  // ----------------------------------------------------------------------- //

  function handleAddTexts(
    rawTexts: { text: string; name: string }[],
    source: string,
  ) {
    if (!project) return;
    const cleaned = rawTexts.filter((r) => r.text.trim().length > 0);
    if (cleaned.length === 0) {
      setErrorData({ title: t("textAnnotation.errors.invalidText") });
      return;
    }
    postTasks(
      { projectId: project.id, tasks: cleaned, source },
      {
        onError: (error) =>
          setErrorData({
            title: t("textAnnotation.errors.addTexts"),
            list: [error.message],
          }),
      },
    );
  }

  function handleUploadFiles(files: FileList | File[]) {
    const fileArr = Array.from(files).filter(
      (f) => /\.(txt|md)$/i.test(f.name) || f.type.startsWith("text/"),
    );
    if (fileArr.length === 0) {
      setErrorData({ title: t("textAnnotation.errors.invalidText") });
      return;
    }
    Promise.all(fileArr.map(readFileAsText)).then((texts) => {
      handleAddTexts(
        texts.map((text, i) => ({
          text,
          name: fileArr[i]?.name ?? `text-${i}`,
        })),
        "text_file",
      );
    });
  }

  function handleAddPastedText() {
    const text = importText.trim();
    if (!text) return;
    handleAddTexts([{ text, name: `text-${tasks.length + 1}` }], "paste");
    setImportText("");
  }

  function handleDeleteTask(task: TextAnnotationTaskItemType) {
    if (!project) return;
    deleteTask(
      { projectId: project.id, taskId: task.id },
      {
        onSuccess: () => {
          if (activeTaskId === task.id) {
            setActiveTaskId(null);
            setSelectedSpanId(null);
          }
        },
        onError: (error) =>
          setErrorData({
            title: t("textAnnotation.errors.deleteTask"),
            list: [error.message],
          }),
      },
    );
  }

  // ----------------------------------------------------------------------- //
  // Annotation handlers
  // ----------------------------------------------------------------------- //

  function handleCreateSpanFromSelection(label?: string) {
    const container = textContainerRef.current;
    const effectiveLabel = label ?? activeLabel;
    if (!container || !activeTask || !effectiveLabel) return;
    const offsets = getSelectionOffsets(container);
    if (!offsets) return;
    const span: TextSpan = {
      id: genSpanId(),
      start: offsets.start,
      end: offsets.end,
      text: activeTask.text.slice(offsets.start, offsets.end),
      label: effectiveLabel,
    };
    updateDraft(activeTask.id, (draft) => ({
      ...draft,
      spans: [...draft.spans, span],
    }));
    setSelectedSpanId(span.id);
    window.getSelection()?.removeAllRanges();
  }

  function handleLabelClick(label: string) {
    setActiveLabel(label);
    handleCreateSpanFromSelection(label);
  }

  function handleLabelColorChange(label: string, color: string) {
    if (!project) return;
    const nextLabels: TextAnnotationLabel[] = project.entity_labels.map(
      (entry) =>
        entry.value === label ? { ...entry, background: color } : entry,
    );
    patchProject(
      { projectId: project.id, entity_labels: nextLabels },
      {
        onError: (error) =>
          setErrorData({
            title: t("textAnnotation.errors.updateProject"),
            list: [error.message],
          }),
      },
    );
  }

  function handleDeleteSpan(id: string) {
    if (!activeTask) return;
    updateDraft(activeTask.id, (draft) => ({
      ...draft,
      spans: draft.spans.filter((s) => s.id !== id),
    }));
    if (selectedSpanId === id) setSelectedSpanId(null);
  }

  function handleSpanLabelChange(id: string, label: string) {
    if (!activeTask) return;
    updateDraft(activeTask.id, (draft) => ({
      ...draft,
      spans: draft.spans.map((s) => (s.id === id ? { ...s, label } : s)),
    }));
  }

  function handleToggleCategory(label: string) {
    if (!activeTask) return;
    updateDraft(activeTask.id, (draft) => {
      const has = draft.categories.includes(label);
      return {
        ...draft,
        categories: has
          ? draft.categories.filter((c) => c !== label)
          : [...draft.categories, label],
      };
    });
  }

  function handleClearAll() {
    if (!activeTask) return;
    updateDraft(activeTask.id, () => ({ spans: [], categories: [] }));
    setSelectedSpanId(null);
  }

  function handleSave() {
    if (!project || !activeTask) return;
    const result =
      project.task_type === "ner"
        ? spansToRegions(activeDraft.spans)
        : categoriesToRegions(activeDraft.categories);
    putAnnotations(
      { projectId: project.id, taskId: activeTask.id, result },
      {
        onSuccess: () => {
          setDirtyTasks((prev) => ({ ...prev, [activeTask.id]: false }));
          setSuccessData({
            title: t("textAnnotation.success.annotationsSaved"),
          });
        },
        onError: (error) =>
          setErrorData({
            title: t("textAnnotation.errors.saveAnnotations"),
            list: [error.message],
          }),
      },
    );
  }

  function handlePrev() {
    if (activeIndex > 0) {
      setActiveTaskId(tasks[activeIndex - 1].id);
      setSelectedSpanId(null);
    }
  }

  function handleNext() {
    if (activeIndex >= 0 && activeIndex < tasks.length - 1) {
      setActiveTaskId(tasks[activeIndex + 1].id);
      setSelectedSpanId(null);
    }
  }

  const segments = useMemo(() => {
    if (!activeTask) return [];
    return buildSegments(activeTask.text, activeDraft.spans);
  }, [activeTask, activeDraft.spans]);

  // ----------------------------------------------------------------------- //
  // Render states
  // ----------------------------------------------------------------------- //

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <CustomLoader remSize={12} />
      </div>
    );
  }

  if (isError || !project) {
    return (
      <div className="admin-page-panel flex h-full flex-col items-center justify-center gap-3 pb-8">
        <IconComponent
          name="FileText"
          className="h-10 w-10 text-muted-foreground"
        />
        <span className="text-muted-foreground">
          {t("textAnnotation.errors.projectNotFound")}
        </span>
        <Button variant="primary" onClick={() => navigate("/text-annotation")}>
          {t("textAnnotation.editorBack")}
        </Button>
      </div>
    );
  }

  const isNer = project.task_type === "ner";

  return (
    <div className="flex h-full flex-col">
      <div className="main-page-nav-arrangement">
        <span className="main-page-nav-title">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <IconComponent name="ChevronLeft" className="w-5" />
          </Button>
          <IconComponent name="FileText" className="w-6" />
          <span className="truncate">{project.name}</span>
        </span>
      </div>
      <span className="admin-page-description-text">
        {t("textAnnotation.editorProgress", {
          done: progress.done,
          total: progress.total,
        })}
      </span>

      <div className="flex w-full flex-1 gap-3 overflow-hidden">
        <div className="flex w-60 shrink-0 flex-col overflow-y-auto rounded-md border bg-background custom-scroll">
          <div className="sticky top-0 bg-background p-2 text-sm font-medium">
            {t("textAnnotation.editorTaskList")}
          </div>
          <div className="flex flex-col gap-2 border-b p-2">
            <textarea
              className="primary-input min-h-[80px] resize-y text-xs"
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder={t("textAnnotation.editorPasteHint")}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleAddPastedText}
              disabled={!importText.trim()}
            >
              <IconComponent name="Plus" className="h-4 w-4" />
              {t("textAnnotation.editorAddText")}
            </Button>
            <div className="grid grid-cols-3 gap-1">
              <label className="cursor-pointer">
                <input
                  type="file"
                  accept="text/plain,.txt,.md"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files) handleUploadFiles(e.target.files);
                    e.target.value = "";
                  }}
                />
                <ShadTooltip content={t("textAnnotation.editorUploadText")}>
                  <span className="flex items-center justify-center gap-1 rounded-md border border-dashed px-1 py-2 text-xs text-muted-foreground hover:bg-muted">
                    <IconComponent name="Upload" className="h-4 w-4" />
                  </span>
                </ShadTooltip>
              </label>
              <ImportCsvModal projectId={project.id}>
                <span className="flex cursor-pointer items-center justify-center gap-1 rounded-md border border-dashed px-1 py-2 text-xs text-muted-foreground hover:bg-muted">
                  <ShadTooltip content={t("textAnnotation.importCsvButton")}>
                    <IconComponent name="FileSpreadsheet" className="h-4 w-4" />
                  </ShadTooltip>
                </span>
              </ImportCsvModal>
              <ImportDatabaseModal projectId={project.id}>
                <span className="flex cursor-pointer items-center justify-center gap-1 rounded-md border border-dashed px-1 py-2 text-xs text-muted-foreground hover:bg-muted">
                  <ShadTooltip content={t("textAnnotation.importDbButton")}>
                    <IconComponent name="Database" className="h-4 w-4" />
                  </ShadTooltip>
                </span>
              </ImportDatabaseModal>
            </div>
          </div>
          {tasks.length === 0 ? (
            <div className="p-2 text-xs text-muted-foreground">
              {t("textAnnotation.editorNoTexts")}
            </div>
          ) : (
            tasks.map((task, i) => {
              const draft = getDraft(task);
              const isDirty = dirtyTasks[task.id] ?? false;
              return (
                <div
                  key={task.id}
                  onClick={() => {
                    setActiveTaskId(task.id);
                    setSelectedSpanId(null);
                  }}
                  className={
                    "group flex cursor-pointer items-center gap-2 border-b p-2 text-left text-xs hover:bg-muted " +
                    (task.id === activeTaskId ? "bg-muted" : "")
                  }
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1 truncate">
                      {isDirty && (
                        <ShadTooltip
                          content={t("textAnnotation.editorUnsaved")}
                        >
                          <span className="h-2 w-2 shrink-0 rounded-full bg-accent-amber-foreground" />
                        </ShadTooltip>
                      )}
                      <span className="truncate">{task.name}</span>
                    </div>
                    <div className="truncate text-muted-foreground">
                      {task.text.slice(0, 30)}
                      {task.text.length > 30 ? "..." : ""}
                    </div>
                    {isNer && (
                      <div className="text-muted-foreground">
                        {draft.spans.length}{" "}
                        {t("textAnnotation.editorSpanCount")}
                      </div>
                    )}
                  </div>
                  <ShadTooltip
                    content={t("textAnnotation.editorDeleteTask")}
                  >
                    <button
                      className="flex h-5 w-5 shrink-0 items-center justify-center rounded opacity-0 transition-opacity hover:bg-destructive/10 group-hover:pointer-events-auto group-hover:opacity-100 pointer-events-none"
                      onClick={(e) => {
                        e.stopPropagation();
                        setTaskToDelete(task);
                      }}
                      data-testid="delete-task-button"
                    >
                      <IconComponent
                        name="Trash2"
                        className="h-3.5 w-3.5 text-destructive"
                      />
                    </button>
                  </ShadTooltip>
                  <span className="text-muted-foreground">{i + 1}</span>
                </div>
              );
            })
          )}
        </div>

        <SimpleSidebarProvider
          width="320px"
          defaultOpen
          minWidth={0.15}
          maxWidth={0.4}
          className="flex-1 overflow-hidden"
        >
          <SimpleSidebar side="left" className="border-r bg-background">
            <SimpleSidebarHeader>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">
                  {isNer
                    ? t("textAnnotation.editorEntityLabels")
                    : t("textAnnotation.editorCategories")}
                </span>
                <SidebarCloseButton />
              </div>
            </SimpleSidebarHeader>
            <SimpleSidebarContent className="px-0">
              {isNer && (
                <>
                  <div className="flex flex-col gap-1 border-b p-2">
                    {entityLabelNames.length === 0 ? (
                      <span className="text-xs text-muted-foreground">
                        {t("textAnnotation.editorNoLabels")}
                      </span>
                    ) : (
                      entityLabelNames.map((label) => (
                        <div key={label} className="flex items-center gap-2">
                          <LabelColorPicker
                            color={colorForLabel(
                              label,
                              entityLabelNames,
                              labelColors,
                            )}
                            onChange={(c) => handleLabelColorChange(label, c)}
                          />
                          <button
                            onClick={() => setActiveLabel(label)}
                            className={
                              "min-w-0 flex-1 rounded px-2 py-0.5 text-left text-xs text-white " +
                              (label === activeLabel
                                ? "ring-2 ring-foreground ring-offset-1"
                                : "")
                            }
                            style={{
                              backgroundColor: colorForLabel(
                                label,
                                entityLabelNames,
                                labelColors,
                              ),
                            }}
                          >
                            {label}
                          </button>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="border-b p-2 text-sm font-medium">
                    {t("textAnnotation.editorSpanList")}
                  </div>
                  <div className="flex-1 overflow-y-auto">
                    {!activeTask || activeDraft.spans.length === 0 ? (
                      <div className="p-3 text-xs text-muted-foreground">
                        {t("textAnnotation.editorNoSpan")}
                      </div>
                    ) : (
                      activeDraft.spans.map((s) => {
                        const color = colorForLabel(
                          s.label,
                          entityLabelNames,
                          labelColors,
                        );
                        return (
                          <div
                            key={s.id}
                            className={
                              "flex items-center gap-2 border-b p-2 text-xs " +
                              (s.id === selectedSpanId ? "bg-muted" : "")
                            }
                            onClick={() => setSelectedSpanId(s.id)}
                          >
                            <span
                              className="h-3 w-3 shrink-0 rounded"
                              style={{ backgroundColor: color }}
                            />
                            <select
                              value={s.label}
                              onChange={(e) =>
                                handleSpanLabelChange(s.id, e.target.value)
                              }
                              className="primary-input min-w-0 flex-1 py-1 text-xs"
                            >
                              {entityLabelNames.map((l) => (
                                <option key={l} value={l}>
                                  {l}
                                </option>
                              ))}
                            </select>
                            <ShadTooltip
                              content={t("textAnnotation.editorDeleteSpan")}
                            >
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteSpan(s.id);
                                }}
                                className="shrink-0"
                              >
                                <IconComponent
                                  name="Trash2"
                                  className="h-3.5 w-3.5 cursor-pointer text-destructive"
                                />
                              </button>
                            </ShadTooltip>
                          </div>
                        );
                      })
                    )}
                  </div>
                </>
              )}

              {!isNer && (
                <div className="flex flex-col gap-1 p-2">
                  {categoryLabelNames.length === 0 ? (
                    <span className="text-xs text-muted-foreground">
                      {t("textAnnotation.editorNoCategories")}
                    </span>
                  ) : (
                    categoryLabelNames.map((label) => {
                      const checked = activeDraft.categories.includes(label);
                      return (
                        <label
                          key={label}
                          className="flex cursor-pointer items-center gap-2 text-xs"
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4"
                            checked={checked}
                            onChange={() => handleToggleCategory(label)}
                          />
                          <span>{label}</span>
                        </label>
                      );
                    })
                  )}
                </div>
              )}
            </SimpleSidebarContent>
          </SimpleSidebar>

          <div className="flex flex-1 flex-col overflow-hidden">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex flex-1 items-center gap-2 overflow-hidden">
                <SidebarToggle />
                {isNer && (
                  <ShadTooltip content={t("textAnnotation.editorNoSelection")}>
                    <div className="flex flex-wrap items-center gap-1">
                      {entityLabelNames.length === 0 ? (
                        <span className="text-xs text-muted-foreground">
                          {t("textAnnotation.editorNoLabels")}
                        </span>
                      ) : (
                        entityLabelNames.map((label) => (
                          <button
                            key={label}
                            onClick={() => handleLabelClick(label)}
                            className={
                              "rounded px-2 py-0.5 text-xs text-white " +
                              (label === activeLabel
                                ? "ring-2 ring-foreground ring-offset-1"
                                : "")
                            }
                            style={{
                              backgroundColor: colorForLabel(
                                label,
                                entityLabelNames,
                                labelColors,
                              ),
                            }}
                          >
                            {label}
                          </button>
                        ))
                      )}
                    </div>
                  </ShadTooltip>
                )}
                <ShadTooltip content={t("textAnnotation.editorClearAll")}>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={handleClearAll}
                    disabled={
                      !activeTask ||
                      (activeDraft.spans.length === 0 &&
                        activeDraft.categories.length === 0)
                    }
                  >
                    <IconComponent name="Eraser" className="h-4 w-4" />
                  </Button>
                </ShadTooltip>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrev}
                  disabled={activeIndex <= 0}
                >
                  <IconComponent name="ChevronLeft" className="h-4 w-4" />
                  {t("textAnnotation.editorPrev")}
                </Button>
                <span className="text-sm text-muted-foreground">
                  {activeIndex + 1} / {tasks.length}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNext}
                  disabled={activeIndex >= tasks.length - 1}
                >
                  {t("textAnnotation.editorNext")}
                  <IconComponent name="ChevronRight" className="h-4 w-4" />
                </Button>
              </div>
              <ExportAnnotationsModal
                projectId={project.id}
                projectName={project.name}
                taskType={project.task_type}
              >
                <Button variant="outline" size="sm">
                  <IconComponent name="Download" className="h-4 w-4" />
                  {t("textAnnotation.exportButton")}
                </Button>
              </ExportAnnotationsModal>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSave}
                disabled={!activeTask || !(dirtyTasks[activeTask.id] ?? false)}
                loading={isSaving}
              >
                <IconComponent name="Save" className="h-4 w-4" />
                {t("textAnnotation.editorSave")}
              </Button>
            </div>

            <div className="flex flex-1 overflow-auto rounded-md border bg-background custom-scroll">
              {!activeTask ? (
                <div className="flex h-full w-full flex-col items-center justify-center gap-3 p-6 text-center text-muted-foreground">
                  <IconComponent name="FileText" className="h-10 w-10" />
                  <span>{t("textAnnotation.editorNoTexts")}</span>
                </div>
              ) : (
                <div
                  ref={textContainerRef}
                  className="w-full select-text whitespace-pre-wrap p-4 text-sm leading-7"
                >
                  {segments.map((seg) => {
                    const isSelected = seg.spans.some(
                      (s) => s.id === selectedSpanId,
                    );
                    const primary =
                      seg.spans.find((s) => s.id === selectedSpanId) ??
                      seg.spans[0];
                    const bg = primary
                      ? colorForLabel(
                          primary.label,
                          entityLabelNames,
                          labelColors,
                        )
                      : "transparent";
                    return (
                      <span
                        key={`${seg.start}-${seg.end}`}
                        data-start={seg.start}
                        data-end={seg.end}
                        style={{
                          backgroundColor: bg,
                          borderRadius: "2px",
                          boxShadow: isSelected
                            ? `0 0 0 1.5px ${bg}`
                            : undefined,
                          cursor: "text",
                        }}
                        onClick={() => {
                          if (primary) setSelectedSpanId(primary.id);
                        }}
                      >
                        {seg.text}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </SimpleSidebarProvider>
      </div>

      <ConfirmationModal
        size="x-small"
        title={t("textAnnotation.deleteProjectTitle")}
        titleHeader={t("textAnnotation.editorDeleteTask")}
        modalContentTitle={taskToDelete?.name ?? ""}
        cancelText={t("textAnnotation.cancelButton")}
        confirmationText={t("textAnnotation.deleteProjectTitle")}
        icon="Trash2"
        data={taskToDelete}
        open={taskToDelete !== null}
        onConfirm={() => {
          if (taskToDelete) handleDeleteTask(taskToDelete);
          setTaskToDelete(null);
        }}
        onCancel={() => setTaskToDelete(null)}
        onClose={() => setTaskToDelete(null)}
      >
        <ConfirmationModal.Content>
          <span>{t("textAnnotation.deleteTaskConfirm")}</span>
        </ConfirmationModal.Content>
      </ConfirmationModal>
    </div>
  );
}

function SidebarToggle() {
  const { t } = useTranslation();
  const { open, toggleSidebar } = useSimpleSidebar();
  return (
    <ShadTooltip content={t("textAnnotation.editorToggleLabelPanel")}>
      <Button
        variant="outline"
        size="icon"
        onClick={toggleSidebar}
        data-testid="toggle-label-panel"
      >
        <IconComponent
          name={open ? "PanelLeftClose" : "PanelLeftOpen"}
          className="h-4 w-4"
        />
      </Button>
    </ShadTooltip>
  );
}

function SidebarCloseButton() {
  const { t } = useTranslation();
  const { setOpen } = useSimpleSidebar();
  return (
    <ShadTooltip content={t("textAnnotation.editorToggleLabelPanel")}>
      <Button variant="ghost" size="icon" onClick={() => setOpen(false)}>
        <IconComponent name="PanelLeftClose" className="h-4 w-4" />
      </Button>
    </ShadTooltip>
  );
}
