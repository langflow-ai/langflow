import { useCallback } from "react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import {
  findStarterTemplate,
  type StarterTemplateNameKey,
} from "../helpers/find-starter-template";

/**
 * Returns an apply function that swaps the CURRENT flow's nodes/edges with a
 * starter template's data, identified by its stable ``name_key``. Intended
 * for the welcome overlay's quick-template buttons — the current flow has
 * already been created (empty) and we're populating it in place rather than
 * creating a second flow.
 *
 * Returns ``true`` on success, ``false`` when the requested template wasn't
 * found in the loaded examples (e.g. examples list not loaded yet). Callers
 * should branch on the boolean to decide whether to close the overlay.
 */
export function useApplyTemplateToCurrentFlow() {
  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const reactFlowInstance = useFlowStore((state) => state.reactFlowInstance);
  const examples = useFlowsManagerStore((state) => state.examples);

  return useCallback(
    (nameKey: StarterTemplateNameKey, onFitted?: () => void): boolean => {
      const template = findStarterTemplate(examples, nameKey);
      if (!template?.data) return false;
      setNodes(template.data.nodes ?? []);
      setEdges(template.data.edges ?? []);
      // Why this dance:
      //   1. ReactFlow can only compute the correct viewport AFTER the new
      //      nodes have rendered AND been measured — node widths/heights are
      //      read from the DOM, not the data.
      //   2. So we wait two rAFs: first for React to commit setNodes/setEdges,
      //      then for ReactFlow to lay out the new nodes.
      //   3. We call ``fitView`` with NO ``duration`` so the camera SNAPS to
      //      the right viewport — the welcome overlay is still covering the
      //      canvas at this point, so the snap is invisible to the user.
      //   4. ``onFitted`` (the welcome's ``close``) runs on the next frame,
      //      revealing an already-fit canvas instead of an animated camera
      //      flying into place.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          reactFlowInstance?.fitView({
            padding: { left: "20px", right: "20px", top: "80px" },
          });
          requestAnimationFrame(() => onFitted?.());
        });
      });
      return true;
    },
    [examples, setNodes, setEdges, reactFlowInstance],
  );
}
