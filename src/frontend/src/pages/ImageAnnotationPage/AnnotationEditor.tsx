import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  useDeleteAnnotationImage,
  useGetAnnotationImageUrl,
  useGetAnnotationProject,
  useGetImageAnnotations,
  usePatchAnnotationImage,
  usePostAnnotationImages,
  usePutImageAnnotations,
} from "@/controllers/API/queries/annotation";
import CustomLoader from "@/customization/components/custom-loader";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import { Button } from "../../components/ui/button";
import ConfirmationModal from "../../modals/confirmationModal";
import {
  type AnnotationImageType,
  type AnnotationLabel,
  type AnnotationRegion,
  colorForLabel,
  createRegion,
  type RectPct,
} from "./types";

type Tool = "select" | "rect";

type DraftRect = {
  xPct: number;
  yPct: number;
  wPct: number;
  hPct: number;
};

type Interaction =
  | { kind: "draw" }
  | {
      kind: "move";
      regionId: string;
      startX: number;
      startY: number;
      orig: RectPct;
    }
  | {
      kind: "resize";
      regionId: string;
      handle: string;
      startX: number;
      startY: number;
      orig: RectPct;
    };

const RESIZE_HANDLES = ["nw", "n", "ne", "e", "se", "s", "sw", "w"] as const;

const HANDLE_CURSORS: Record<string, string> = {
  nw: "nwse-resize",
  se: "nwse-resize",
  ne: "nesw-resize",
  sw: "nesw-resize",
  n: "ns-resize",
  s: "ns-resize",
  e: "ew-resize",
  w: "ew-resize",
};

function clampRect(rect: RectPct): RectPct {
  const width = Math.max(0.5, Math.min(rect.width, 100));
  const height = Math.max(0.5, Math.min(rect.height, 100));
  return {
    x: Math.max(0, Math.min(rect.x, 100 - width)),
    y: Math.max(0, Math.min(rect.y, 100 - height)),
    width,
    height,
  };
}

function applyResize(
  orig: RectPct,
  handle: string,
  dx: number,
  dy: number,
): RectPct {
  let { x, y, width, height } = orig;
  if (handle.includes("e")) width = orig.width + dx;
  if (handle.includes("s")) height = orig.height + dy;
  if (handle.includes("w")) {
    x = orig.x + dx;
    width = orig.width - dx;
  }
  if (handle.includes("n")) {
    y = orig.y + dy;
    height = orig.height - dy;
  }
  if (width < 0.5) {
    if (handle.includes("w")) x = orig.x + orig.width - 0.5;
    width = 0.5;
  }
  if (height < 0.5) {
    if (handle.includes("n")) y = orig.y + orig.height - 0.5;
    height = 0.5;
  }
  return clampRect({ x, y, width, height });
}

function regionToRect(region: AnnotationRegion): RectPct {
  return {
    x: region.value.x,
    y: region.value.y,
    width: region.value.width,
    height: region.value.height,
  };
}

function handlePosition(
  rect: RectPct,
  handle: string,
): { left: string; top: string } {
  const x = handle.includes("w")
    ? rect.x
    : handle.includes("e")
      ? rect.x + rect.width
      : rect.x + rect.width / 2;
  const y = handle.includes("n")
    ? rect.y
    : handle.includes("s")
      ? rect.y + rect.height
      : rect.y + rect.height / 2;
  return { left: `${x}%`, top: `${y}%` };
}

function TaskThumbnail({
  projectId,
  imageId,
  alt,
}: {
  projectId: string;
  imageId: string;
  alt: string;
}) {
  const { data: url } = useGetAnnotationImageUrl({ projectId, imageId });
  if (!url) {
    return (
      <div className="h-10 w-10 shrink-0 animate-pulse rounded bg-muted" />
    );
  }
  return (
    <img
      src={url}
      alt={alt}
      className="h-10 w-10 shrink-0 rounded object-cover"
    />
  );
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
  } = useGetAnnotationProject({ projectId });

  const images = useMemo(() => project?.images ?? [], [project]);
  const labels = useMemo(() => project?.labels ?? [], [project]);

  const [activeImageId, setActiveImageId] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool>("rect");
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftRect | null>(null);
  const [regions, setRegions] = useState<AnnotationRegion[]>([]);
  const [savedRegions, setSavedRegions] = useState<AnnotationRegion[]>([]);
  const [activeLabel, setActiveLabel] = useState<string>("");
  const [naturalSize, setNaturalSize] = useState<{
    w: number;
    h: number;
  } | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const interactionRef = useRef<Interaction | null>(null);
  const imageOpenedAtRef = useRef<number>(Date.now());

  // Keep the active image valid as the image list changes (upload/delete).
  useEffect(() => {
    if (images.length === 0) {
      setActiveImageId(null);
      return;
    }
    if (!activeImageId || !images.some((img) => img.id === activeImageId)) {
      setActiveImageId(images[0]?.id ?? null);
    }
  }, [images, activeImageId]);

  // Default active label once labels load.
  useEffect(() => {
    if (!activeLabel && labels.length > 0) {
      setActiveLabel(labels[0]?.value ?? "");
    }
  }, [labels, activeLabel]);

  const activeImage: AnnotationImageType | null = useMemo(
    () => images.find((img) => img.id === activeImageId) ?? null,
    [images, activeImageId],
  );

  const activeIndex = useMemo(() => {
    if (!activeImage) return -1;
    return images.findIndex((img) => img.id === activeImage.id);
  }, [images, activeImage]);

  // Load the active image's saved annotations into the editing state.
  const { data: annotationsData } = useGetImageAnnotations({
    projectId,
    imageId: activeImageId,
  });
  useEffect(() => {
    const result = annotationsData?.result ?? [];
    setRegions(result);
    setSavedRegions(result);
    setSelectedRegionId(null);
    imageOpenedAtRef.current = Date.now();
  }, [annotationsData]);

  const isDirty = useMemo(
    () => JSON.stringify(regions) !== JSON.stringify(savedRegions),
    [regions, savedRegions],
  );

  const { data: activeImageUrl } = useGetAnnotationImageUrl({
    projectId,
    imageId: activeImageId,
  });

  const { mutate: uploadImages, isPending: isUploading } =
    usePostAnnotationImages({
      onSuccess: (data) => {
        setSuccessData({
          title: t("imageAnnotation.success.imageUploaded"),
        });
        if (data.length > 0) setActiveImageId(data[0].id);
      },
      onError: (error) =>
        setErrorData({
          title: t("imageAnnotation.errors.uploadImage"),
          list: [error.message],
        }),
    });

  const { mutate: deleteImage } = useDeleteAnnotationImage({
    onSuccess: () =>
      setSuccessData({ title: t("imageAnnotation.success.imageDeleted") }),
    onError: (error) =>
      setErrorData({
        title: t("imageAnnotation.errors.deleteImage"),
        list: [error.message],
      }),
  });

  const { mutate: patchImage } = usePatchAnnotationImage({});

  const { mutate: putAnnotations, isPending: isSaving } =
    usePutImageAnnotations({
      onError: (error) =>
        setErrorData({
          title: t("imageAnnotation.errors.saveAnnotations"),
          list: [error.message],
        }),
    });

  const updateRegionRect = useCallback((regionId: string, rect: RectPct) => {
    setRegions((prev) =>
      prev.map((region) =>
        region.id === regionId
          ? { ...region, value: { ...region.value, ...rect } }
          : region,
      ),
    );
  }, []);

  function getRelativePoint(e: React.MouseEvent): {
    xPct: number;
    yPct: number;
  } | null {
    const el = containerRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    const xPct = ((e.clientX - rect.left) / rect.width) * 100;
    const yPct = ((e.clientY - rect.top) / rect.height) * 100;
    return {
      xPct: Math.max(0, Math.min(100, xPct)),
      yPct: Math.max(0, Math.min(100, yPct)),
    };
  }

  function handleMouseDown(e: React.MouseEvent) {
    if (tool === "select") {
      setSelectedRegionId(null);
      return;
    }
    if (!activeImage) return;
    const pt = getRelativePoint(e);
    if (!pt) return;
    interactionRef.current = { kind: "draw" };
    setDraft({ xPct: pt.xPct, yPct: pt.yPct, wPct: 0, hPct: 0 });
    setSelectedRegionId(null);
  }

  function handleRegionMouseDown(
    e: React.MouseEvent,
    region: AnnotationRegion,
  ) {
    if (tool !== "select") return;
    e.stopPropagation();
    const pt = getRelativePoint(e);
    if (!pt) return;
    setSelectedRegionId(region.id);
    interactionRef.current = {
      kind: "move",
      regionId: region.id,
      startX: pt.xPct,
      startY: pt.yPct,
      orig: regionToRect(region),
    };
  }

  function handleResizeMouseDown(
    e: React.MouseEvent,
    region: AnnotationRegion,
    handle: string,
  ) {
    if (tool !== "select") return;
    e.stopPropagation();
    const pt = getRelativePoint(e);
    if (!pt) return;
    interactionRef.current = {
      kind: "resize",
      regionId: region.id,
      handle,
      startX: pt.xPct,
      startY: pt.yPct,
      orig: regionToRect(region),
    };
  }

  function handleMouseMove(e: React.MouseEvent) {
    const interaction = interactionRef.current;
    if (!interaction) return;
    const pt = getRelativePoint(e);
    if (!pt) return;

    if (interaction.kind === "draw") {
      setDraft((prev) =>
        prev
          ? { ...prev, wPct: pt.xPct - prev.xPct, hPct: pt.yPct - prev.yPct }
          : prev,
      );
      return;
    }
    const dx = pt.xPct - interaction.startX;
    const dy = pt.yPct - interaction.startY;
    if (interaction.kind === "move") {
      updateRegionRect(
        interaction.regionId,
        clampRect({
          x: interaction.orig.x + dx,
          y: interaction.orig.y + dy,
          width: interaction.orig.width,
          height: interaction.orig.height,
        }),
      );
    } else {
      updateRegionRect(
        interaction.regionId,
        applyResize(interaction.orig, interaction.handle, dx, dy),
      );
    }
  }

  function handleMouseUp() {
    const interaction = interactionRef.current;
    interactionRef.current = null;
    if (!interaction) return;
    if (interaction.kind !== "draw") return;
    if (!draft || !activeImage) {
      setDraft(null);
      return;
    }
    const w = Math.abs(draft.wPct);
    const h = Math.abs(draft.hPct);
    if (w < 1 || h < 1) {
      setDraft(null);
      return;
    }
    const rect: RectPct = {
      x: draft.wPct < 0 ? draft.xPct + draft.wPct : draft.xPct,
      y: draft.hPct < 0 ? draft.yPct + draft.hPct : draft.yPct,
      width: w,
      height: h,
    };
    const region = createRegion(
      rect,
      activeLabel,
      naturalSize?.w ?? activeImage.width,
      naturalSize?.h ?? activeImage.height,
    );
    setRegions((prev) => [...prev, region]);
    setDraft(null);
    setSelectedRegionId(region.id);
  }

  function handleDeleteRegion(id: string) {
    setRegions((prev) => prev.filter((region) => region.id !== id));
    if (selectedRegionId === id) setSelectedRegionId(null);
  }

  function handleRegionLabelChange(id: string, label: string) {
    setRegions((prev) =>
      prev.map((region) =>
        region.id === id
          ? {
              ...region,
              value: { ...region.value, rectanglelabels: label ? [label] : [] },
            }
          : region,
      ),
    );
  }

  function handleClearAll() {
    setRegions([]);
    setSelectedRegionId(null);
  }

  function handleSave() {
    if (!activeImage) return;
    const stamped = regions.map((region) =>
      region.original_width && region.original_height
        ? region
        : {
            ...region,
            original_width: naturalSize?.w ?? null,
            original_height: naturalSize?.h ?? null,
          },
    );
    putAnnotations(
      {
        projectId,
        imageId: activeImage.id,
        result: stamped,
        lead_time: (Date.now() - imageOpenedAtRef.current) / 1000,
      },
      {
        onSuccess: () => {
          setSavedRegions(stamped);
          setRegions(stamped);
          setSuccessData({
            title: t("imageAnnotation.success.annotationsSaved"),
          });
        },
      },
    );
  }

  function confirmDiscardChanges(): boolean {
    if (!isDirty) return true;
    return window.confirm(t("imageAnnotation.editorDiscardChangesConfirm"));
  }

  function switchImage(imageId: string) {
    if (imageId === activeImageId) return;
    if (!confirmDiscardChanges()) return;
    setActiveImageId(imageId);
    setSelectedRegionId(null);
    setDraft(null);
  }

  function handlePrev() {
    if (activeIndex > 0) switchImage(images[activeIndex - 1].id);
  }

  function handleNext() {
    if (activeIndex >= 0 && activeIndex < images.length - 1) {
      switchImage(images[activeIndex + 1].id);
    }
  }

  function handleAddImages(fileList: FileList | File[]) {
    const fileArr = Array.from(fileList).filter((f) =>
      f.type.startsWith("image/"),
    );
    if (fileArr.length === 0) {
      setErrorData({ title: t("imageAnnotation.errors.invalidImage") });
      return;
    }
    uploadImages({ projectId, files: fileArr });
  }

  function handleImageLoaded(e: React.SyntheticEvent<HTMLImageElement>) {
    const img = e.currentTarget;
    const size = { w: img.naturalWidth, h: img.naturalHeight };
    setNaturalSize(size);
    if (activeImage && activeImage.width === null && size.w > 0) {
      patchImage({
        projectId,
        imageId: activeImage.id,
        width: size.w,
        height: size.h,
      });
    }
  }

  // Keyboard shortcuts: 1-9 select label, Delete removes selection,
  // Ctrl/Cmd+S saves, arrows switch images.
  useEffect(() => {
    function isFormTarget(target: EventTarget | null): boolean {
      if (!(target instanceof HTMLElement)) return false;
      const tag = target.tagName;
      return (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT" ||
        target.isContentEditable
      );
    }

    function onKeyDown(e: KeyboardEvent) {
      if (isFormTarget(e.target)) return;

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        handleSave();
        return;
      }
      if (e.key >= "1" && e.key <= "9") {
        const label = labels[Number(e.key) - 1]?.value;
        if (label) setActiveLabel(label);
        return;
      }
      if ((e.key === "Delete" || e.key === "Backspace") && selectedRegionId) {
        e.preventDefault();
        handleDeleteRegion(selectedRegionId);
        return;
      }
      if (e.key === "ArrowLeft") {
        handlePrev();
        return;
      }
      if (e.key === "ArrowRight") {
        handleNext();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    labels,
    selectedRegionId,
    activeIndex,
    images,
    isDirty,
    regions,
    activeImage,
    naturalSize,
  ]);

  function normalizedDraft(d: DraftRect) {
    const x = d.wPct < 0 ? d.xPct + d.wPct : d.xPct;
    const y = d.hPct < 0 ? d.yPct + d.hPct : d.yPct;
    return { x, y, w: Math.abs(d.wPct), h: Math.abs(d.hPct) };
  }

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
          name="ImageOff"
          className="h-10 w-10 text-muted-foreground"
        />
        <span className="text-muted-foreground">
          {t("imageAnnotation.noProjects")}
        </span>
        <Button variant="primary" onClick={() => navigate("/image-annotation")}>
          {t("imageAnnotation.editorBack")}
        </Button>
      </div>
    );
  }

  const progress = { done: project.labeled_count, total: project.image_count };

  return (
    <div className="flex h-full flex-col">
      <div className="main-page-nav-arrangement">
        <span className="main-page-nav-title">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/image-annotation")}
          >
            <IconComponent name="ChevronLeft" className="w-5" />
          </Button>
          <IconComponent name="ImagePlus" className="w-6" />
          <span className="truncate">{project.name}</span>
        </span>
      </div>
      <span className="admin-page-description-text">
        {t("imageAnnotation.editorProgress", {
          done: progress.done,
          total: progress.total,
        })}
      </span>

      <div className="flex w-full flex-1 gap-3 overflow-hidden">
        <div className="flex w-48 shrink-0 flex-col overflow-y-auto rounded-md border bg-background custom-scroll">
          <div className="sticky top-0 bg-background p-2 text-sm font-medium">
            {t("imageAnnotation.editorTaskList")}
          </div>
          <label className="m-2 cursor-pointer">
            <input
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              disabled={isUploading}
              onChange={(e) => {
                if (e.target.files) handleAddImages(e.target.files);
                e.target.value = "";
              }}
            />
            <span className="flex items-center justify-center gap-1 rounded-md border border-dashed px-2 py-3 text-xs text-muted-foreground hover:bg-muted">
              <IconComponent name="Upload" className="h-4 w-4" />
              {isUploading
                ? t("imageAnnotation.editorUploading")
                : t("imageAnnotation.editorUploadImage")}
            </span>
          </label>
          {images.length === 0 ? (
            <div className="p-2 text-xs text-muted-foreground">
              {t("imageAnnotation.editorNoImages")}
            </div>
          ) : (
            images.map((image, i) => (
              <div
                key={image.id}
                role="button"
                tabIndex={0}
                onClick={() => switchImage(image.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") switchImage(image.id);
                }}
                className={
                  "flex cursor-pointer items-center gap-2 border-b p-2 text-left text-xs hover:bg-muted " +
                  (image.id === activeImageId ? "bg-muted" : "")
                }
              >
                <TaskThumbnail
                  projectId={projectId}
                  imageId={image.id}
                  alt={image.name}
                />
                <div className="min-w-0 flex-1">
                  <div className="truncate">{image.name}</div>
                  <div className="text-muted-foreground">
                    {image.id === activeImageId
                      ? regions.length
                      : image.annotation_count}{" "}
                    {t("imageAnnotation.editorAnnotationList")}
                  </div>
                </div>
                <ConfirmationModal
                  size="x-small"
                  title={t("imageAnnotation.editorDeleteImage")}
                  titleHeader={t("imageAnnotation.editorDeleteImage")}
                  modalContentTitle={image.name}
                  cancelText={t("imageAnnotation.cancelButton")}
                  confirmationText={t("imageAnnotation.editorDeleteImage")}
                  icon="Trash2"
                  data={image}
                  onConfirm={() =>
                    deleteImage({ projectId, imageId: image.id })
                  }
                >
                  <ConfirmationModal.Content>
                    <span>{t("imageAnnotation.editorDeleteImageConfirm")}</span>
                  </ConfirmationModal.Content>
                  <ConfirmationModal.Trigger>
                    <button
                      className="shrink-0"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <IconComponent
                        name="Trash2"
                        className="h-3.5 w-3.5 cursor-pointer text-destructive"
                      />
                    </button>
                  </ConfirmationModal.Trigger>
                </ConfirmationModal>
                <span className="text-muted-foreground">{i + 1}</span>
              </div>
            ))
          )}
        </div>

        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="flex items-center gap-1">
              <ShadTooltip content={t("imageAnnotation.editorRectTool")}>
                <Button
                  variant={tool === "rect" ? "primary" : "outline"}
                  size="icon"
                  onClick={() => setTool("rect")}
                  data-testid="tool-rect"
                >
                  <IconComponent name="Square" className="h-4 w-4" />
                </Button>
              </ShadTooltip>
              <ShadTooltip content={t("imageAnnotation.editorSelectTool")}>
                <Button
                  variant={tool === "select" ? "primary" : "outline"}
                  size="icon"
                  onClick={() => setTool("select")}
                  data-testid="tool-select"
                >
                  <IconComponent name="MousePointer2" className="h-4 w-4" />
                </Button>
              </ShadTooltip>
              <ShadTooltip content={t("imageAnnotation.editorClearAll")}>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleClearAll}
                  disabled={!activeImage || regions.length === 0}
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
                {t("imageAnnotation.editorPrev")}
              </Button>
              <span className="text-sm text-muted-foreground">
                {activeIndex + 1} / {images.length}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleNext}
                disabled={activeIndex >= images.length - 1}
              >
                {t("imageAnnotation.editorNext")}
                <IconComponent name="ChevronRight" className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex items-center gap-2">
              {isDirty && (
                <span className="text-xs text-status-yellow">
                  {t("imageAnnotation.editorUnsaved")}
                </span>
              )}
              <Button
                variant="primary"
                size="sm"
                onClick={handleSave}
                disabled={!activeImage || isSaving}
              >
                <IconComponent name="Save" className="h-4 w-4" />
                {t("imageAnnotation.editorSave")}
              </Button>
            </div>
          </div>

          <div className="relative flex flex-1 items-center justify-center overflow-auto rounded-md border bg-background custom-scroll">
            {!activeImage ? (
              <div className="flex h-full w-full flex-col items-center justify-center gap-3 p-6 text-center text-muted-foreground">
                <IconComponent name="ImageOff" className="h-10 w-10" />
                <span>{t("imageAnnotation.editorNoImages")}</span>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    disabled={isUploading}
                    onChange={(e) => {
                      if (e.target.files) handleAddImages(e.target.files);
                      e.target.value = "";
                    }}
                  />
                  <span className="inline-flex items-center gap-1 rounded-md border border-dashed px-3 py-2 text-xs hover:bg-muted">
                    <IconComponent name="Upload" className="h-4 w-4" />
                    {t("imageAnnotation.editorUploadImage")}
                  </span>
                </label>
              </div>
            ) : (
              <div
                ref={containerRef}
                className="relative inline-block select-none"
                style={{ cursor: tool === "rect" ? "crosshair" : "default" }}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              >
                {activeImageUrl ? (
                  <img
                    src={activeImageUrl}
                    alt={activeImage.name}
                    className="block max-h-[70vh] max-w-full"
                    draggable={false}
                    onLoad={handleImageLoaded}
                  />
                ) : (
                  <div className="flex h-40 w-60 items-center justify-center">
                    <CustomLoader remSize={6} />
                  </div>
                )}
                <svg
                  className="absolute left-0 top-0 h-full w-full"
                  viewBox="0 0 100 100"
                  preserveAspectRatio="none"
                  style={{ pointerEvents: "none" }}
                >
                  {regions.map((region) => {
                    const rect = regionToRect(region);
                    const labelValue = region.value.rectanglelabels[0] ?? "";
                    const color = colorForLabel(labelValue, labels);
                    const isSelected = region.id === selectedRegionId;
                    return (
                      <g key={region.id}>
                        <rect
                          x={rect.x}
                          y={rect.y}
                          width={rect.width}
                          height={rect.height}
                          fill={color}
                          fillOpacity={isSelected ? 0.25 : 0.15}
                          stroke={color}
                          strokeWidth={isSelected ? 0.6 : 0.4}
                          vectorEffect="non-scaling-stroke"
                        />
                        {labelValue && (
                          <text
                            x={rect.x}
                            y={Math.max(rect.y - 0.5, 1)}
                            fill={color}
                            fontSize={2}
                            fontWeight="bold"
                          >
                            {labelValue}
                          </text>
                        )}
                      </g>
                    );
                  })}
                  {draft &&
                    (() => {
                      const n = normalizedDraft(draft);
                      return (
                        <rect
                          x={n.x}
                          y={n.y}
                          width={n.w}
                          height={n.h}
                          fill="#3b82f6"
                          fillOpacity={0.15}
                          stroke="#3b82f6"
                          strokeWidth={0.5}
                          vectorEffect="non-scaling-stroke"
                        />
                      );
                    })()}
                </svg>
                <div
                  className="absolute inset-0"
                  style={{ pointerEvents: "none" }}
                >
                  {regions.map((region) => {
                    const rect = regionToRect(region);
                    const color = colorForLabel(
                      region.value.rectanglelabels[0] ?? "",
                      labels,
                    );
                    const isSelected = region.id === selectedRegionId;
                    return (
                      <div key={`hit-${region.id}`}>
                        <button
                          onMouseDown={(e) => handleRegionMouseDown(e, region)}
                          onClick={(e) => e.stopPropagation()}
                          className="absolute"
                          style={{
                            left: `${rect.x}%`,
                            top: `${rect.y}%`,
                            width: `${rect.width}%`,
                            height: `${rect.height}%`,
                            pointerEvents: tool === "select" ? "auto" : "none",
                            cursor: tool === "select" ? "move" : "default",
                            border: isSelected ? `2px solid ${color}` : "none",
                            boxSizing: "border-box",
                            background: "transparent",
                          }}
                        />
                        {tool === "select" &&
                          isSelected &&
                          RESIZE_HANDLES.map((handle) => (
                            <button
                              key={handle}
                              onMouseDown={(e) =>
                                handleResizeMouseDown(e, region, handle)
                              }
                              onClick={(e) => e.stopPropagation()}
                              className="absolute h-2.5 w-2.5 rounded-sm border border-background"
                              style={{
                                ...handlePosition(rect, handle),
                                transform: "translate(-50%, -50%)",
                                pointerEvents: "auto",
                                cursor: HANDLE_CURSORS[handle],
                                backgroundColor: color,
                                zIndex: 10,
                              }}
                              aria-label={`resize-${handle}`}
                            />
                          ))}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex w-60 shrink-0 flex-col overflow-y-auto rounded-md border bg-background custom-scroll">
          <div className="border-b p-2 text-sm font-medium">
            {t("imageAnnotation.editorLabels")}
          </div>
          <div className="flex flex-wrap gap-1 border-b p-2">
            {labels.length === 0 ? (
              <span className="text-xs text-muted-foreground">
                {t("imageAnnotation.editorNoLabels")}
              </span>
            ) : (
              labels.map((label: AnnotationLabel, index: number) => (
                <button
                  key={label.value}
                  onClick={() => setActiveLabel(label.value)}
                  className={
                    "rounded px-2 py-0.5 text-xs text-white " +
                    (label.value === activeLabel
                      ? "ring-2 ring-foreground ring-offset-1"
                      : "opacity-70 hover:opacity-100")
                  }
                  style={{
                    backgroundColor: colorForLabel(label.value, labels),
                  }}
                  title={t("imageAnnotation.editorLabelHotkey", {
                    key: index < 9 ? index + 1 : "",
                  })}
                >
                  {index < 9 ? `${index + 1}. ` : ""}
                  {label.value}
                </button>
              ))
            )}
          </div>
          <div className="border-b p-2 text-sm font-medium">
            {t("imageAnnotation.editorAnnotationList")}
          </div>
          <div className="flex-1 overflow-y-auto">
            {!activeImage || regions.length === 0 ? (
              <div className="p-3 text-xs text-muted-foreground">
                {t("imageAnnotation.editorNoAnnotation")}
              </div>
            ) : (
              regions.map((region) => {
                const labelValue = region.value.rectanglelabels[0] ?? "";
                const color = colorForLabel(labelValue, labels);
                return (
                  <div
                    key={region.id}
                    className={
                      "flex items-center gap-2 border-b p-2 text-xs " +
                      (region.id === selectedRegionId ? "bg-muted" : "")
                    }
                    onClick={() => setSelectedRegionId(region.id)}
                  >
                    <span
                      className="h-3 w-3 shrink-0 rounded"
                      style={{ backgroundColor: color }}
                    />
                    <select
                      value={labelValue}
                      onChange={(e) =>
                        handleRegionLabelChange(region.id, e.target.value)
                      }
                      className="primary-input min-w-0 flex-1 py-1 text-xs"
                    >
                      {labels.length === 0 && (
                        <option value="">
                          {t("imageAnnotation.editorLabelPlaceholder")}
                        </option>
                      )}
                      {labels.map((l) => (
                        <option key={l.value} value={l.value}>
                          {l.value}
                        </option>
                      ))}
                    </select>
                    <ShadTooltip
                      content={t("imageAnnotation.editorDeleteAnnotation")}
                    >
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteRegion(region.id);
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
        </div>
      </div>
    </div>
  );
}
