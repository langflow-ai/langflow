import { useCallback, useEffect, useState } from "react";
import { type SidebarSection, useSidebar } from "@/components/ui/sidebar";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
import useFlowBuilderWelcomeStore from "@/stores/flowBuilderWelcomeStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import TemplatesModal from "../../../modals/templatesModal";
import { FlowBuilderWelcome } from "./flow-builder-welcome";
import { useApplyTemplateToCurrentFlow } from "./hooks/use-apply-template-to-current-flow";

/**
 * Renders the FlowBuilderWelcome overlay on the canvas plus the
 * TemplatesModal that "Browse more templates" opens, wiring all four
 * exit paths to the rest of the app:
 *
 *   - Submit text       → stash as ``pendingMessage`` + open AssistantPanel
 *   - Pick a template   → mutate current flow with the template's nodes/edges
 *   - Browse more       → open the existing TemplatesModal locally
 *   - Backdrop / Esc    → close the overlay, leave the blank canvas
 *
 * Mounted inside the FlowPage's canvas wrapper so it overlays the
 * ReactFlow viewport but stays under app-level modals.
 */
export function FlowBuilderWelcomeMount() {
  const isOpen = useFlowBuilderWelcomeStore((state) => state.isOpen);
  const openedForFlowId = useFlowBuilderWelcomeStore(
    (state) => state.openedForFlowId,
  );
  const close = useFlowBuilderWelcomeStore((state) => state.close);
  const setPendingMessage = useFlowBuilderWelcomeStore(
    (state) => state.setPendingMessage,
  );
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const flows = useFlowsManagerStore((state) => state.flows);
  const { deleteFlow } = useDeleteFlow();

  // If the user navigates to a different flow while the welcome is open
  // (e.g. picks a template in the TemplatesModal that spins up a fresh
  // flow), auto-close it. Without this guard the welcome lingers on top of
  // the freshly-loaded canvas it doesn't belong to.
  //
  // The "New Flow" entry point eagerly creates an empty placeholder flow for
  // the welcome to overlay. When the user instead picks a template via "Browse
  // more…", a SECOND flow spins up and we navigate to it — orphaning the blank
  // placeholder. Delete that placeholder here so the user is left with a SINGLE
  // flow (the template they chose) instead of two. Guarded to only remove a
  // still-blank placeholder so we never discard a flow the user built on.
  useEffect(() => {
    if (
      isOpen &&
      openedForFlowId &&
      currentFlowId &&
      currentFlowId !== openedForFlowId
    ) {
      const placeholder = flows?.find((flow) => flow.id === openedForFlowId);
      const isBlankPlaceholder =
        !!placeholder && (placeholder.data?.nodes?.length ?? 0) === 0;
      if (isBlankPlaceholder) {
        // Fire-and-forget: a failed cleanup must not block the close handoff.
        void deleteFlow({ id: openedForFlowId }).catch(() => {});
      }
      close();
    }
  }, [isOpen, openedForFlowId, currentFlowId, close, flows, deleteFlow]);
  const setAssistantSidebarOpen = useAssistantManagerStore(
    (state) => state.setAssistantSidebarOpen,
  );
  const applyTemplate = useApplyTemplateToCurrentFlow();
  // Local — the TemplatesModal is reachable only from the welcome's "Browse
  // more" link, so its open state lives next to the welcome rather than in
  // a global store.
  const [isTemplatesOpen, setIsTemplatesOpen] = useState(false);

  // The real FlowSidebarComponent is hidden via ``display: none`` at the
  // FlowPage level while the welcome is open, so we don't need to touch its
  // open/closed state here. We only need ``setOpen`` and ``setActiveSection``
  // for the rail-click handler below — clicking a rail icon should reveal
  // the real sidebar pre-expanded with the right section selected.
  const { setOpen: setSidebarOpen, setActiveSection } = useSidebar();

  const handleSubmit = useCallback(
    (text: string) => {
      // Order matters here:
      //   1. ``close()`` first — closing also clears ``pendingMessage`` by
      //      design (prevents a stale prompt from replaying next time the
      //      welcome opens), so it MUST run before we stash the new prompt.
      //   2. ``setPendingMessage`` next — primes the AssistantPanel's
      //      open-effect with the freshly-typed prompt.
      //   3. ``setAssistantSidebarOpen(true)`` last — flips the panel on,
      //      causing it to mount AFTER the pending message is already in
      //      the store so its open-effect picks it up on first render.
      close();
      setPendingMessage(text);
      setAssistantSidebarOpen(true);
    },
    [setPendingMessage, setAssistantSidebarOpen, close],
  );

  const handleSelectTemplate = useCallback(
    (nameKey: "simple_agent" | "vector_store_rag") => {
      // Pass ``close`` as the after-fit callback so the welcome stays in
      // front while React commits the nodes and ReactFlow animates fitView.
      // The overlay dismisses on the same frame the camera move starts —
      // smooth handoff instead of a "flash of unfitted canvas".
      const applied = applyTemplate(nameKey, close);
      // ``applyTemplate`` returns false synchronously if the template lookup
      // misses; in that case ``close`` never runs, and the user stays on the
      // welcome with no canvas mutation.
      if (!applied) return;
    },
    [applyTemplate, close],
  );

  const handleBrowseMore = useCallback(() => {
    setIsTemplatesOpen(true);
  }, []);

  // Faux rail icon → open the real sidebar to its FULL expanded view with
  // that section pre-selected, then dismiss the welcome. Order: section
  // first (so the panel opens already showing the right content), then
  // open, then close.
  const handleSelectRailItem = useCallback(
    (section: SidebarSection) => {
      setActiveSection(section);
      setSidebarOpen(true);
      close();
    },
    [setActiveSection, setSidebarOpen, close],
  );

  // Backdrop click / Escape → land the user on the canvas with the real
  // sidebar in its COLLAPSED, icon-only state (matches the minimalist look
  // of the welcome's faux rail). The FlowPage sidebar runs in
  // ``collapsible="icon"`` mode, so ``open=false`` leaves the segmented
  // icon strip visible while hiding the expanded content panel.
  const handleDismiss = useCallback(() => {
    setSidebarOpen(false);
    close();
  }, [setSidebarOpen, close]);

  return (
    <>
      {isOpen && (
        <FlowBuilderWelcome
          onSubmit={handleSubmit}
          onSelectTemplate={handleSelectTemplate}
          onBrowseMore={handleBrowseMore}
          onClose={handleDismiss}
          onSelectRailItem={handleSelectRailItem}
        />
      )}
      {/* Templates modal is mounted alongside the welcome so picking a
          template inside the modal can navigate to its new flow while the
          welcome stays out of the way. The modal handles its own create-
          flow + navigate plumbing — see ``modals/templatesModal``. */}
      {isTemplatesOpen && (
        <TemplatesModal open={isTemplatesOpen} setOpen={setIsTemplatesOpen} />
      )}
    </>
  );
}
