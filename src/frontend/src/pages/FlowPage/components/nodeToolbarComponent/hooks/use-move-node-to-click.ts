import { useReactFlow } from "@xyflow/react";
import { useCallback, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

/**
 * Single-pointer, non-drag node repositioning (WCAG 2.5.7 Dragging
 * Movements, technique F108): arm from the node toolbar, then one click on
 * the canvas pane places the node there. Escape cancels.
 *
 * The pointerdown listener is registered on `document` with capture so it
 * runs before ReactFlow's own pane handler deselects the node (which would
 * unmount the toolbar this hook lives in mid-gesture). Clicks on anything
 * that is not the pane (another node, the sidebar, a modal) cancel the
 * gesture instead of moving the node somewhere surprising.
 */
export function useMoveNodeToClick(nodeId: string) {
  const { t } = useTranslation();
  const { screenToFlowPosition } = useReactFlow();
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const cleanupRef = useRef<(() => void) | null>(null);

  const disarm = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
  }, []);

  useEffect(() => disarm, [disarm]);

  const armMove = useCallback(() => {
    disarm();
    const pane = document.querySelector<HTMLElement>(".react-flow__pane");
    pane?.style.setProperty("cursor", "crosshair");

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target?.classList.contains("react-flow__pane")) {
        disarm();
        return;
      }
      event.preventDefault();
      event.stopPropagation();

      const store = useFlowStore.getState();
      const node = store.nodes.find((candidate) => candidate.id === nodeId);
      if (!node) {
        disarm();
        return;
      }
      const clicked = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      // Center the node on the click rather than hanging it off its
      // top-left corner.
      const position = {
        x: clicked.x - (node.measured?.width ?? 0) / 2,
        y: clicked.y - (node.measured?.height ?? 0) / 2,
      };
      takeSnapshot();
      store.setNode(nodeId, (old) => ({ ...old, position }), false);
      store.autoSaveFlow?.();
      store.updateCurrentFlow({ nodes: useFlowStore.getState().nodes });
      disarm();
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        disarm();
      }
    };

    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("keydown", onKeyDown, true);
    cleanupRef.current = () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("keydown", onKeyDown, true);
      pane?.style.removeProperty("cursor");
    };

    setNoticeData({ title: t("nodeToolbar.moveToArmed") });
  }, [disarm, nodeId, screenToFlowPosition, takeSnapshot, setNoticeData, t]);

  return armMove;
}
