import { useCallback, useRef } from "react";
import { useParams } from "react-router-dom";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAddFlow from "@/hooks/flows/use-add-flow";
import useFlowBuilderWelcomeStore from "@/stores/flowBuilderWelcomeStore";

/**
 * Entry-point for the "New Flow" button on the home page: creates an empty
 * flow on the backend, primes the FlowBuilderWelcome overlay store so the
 * overlay surfaces on the freshly-loaded canvas, then routes the user to
 * the new flow.
 *
 * Replaces the previous behavior of opening the full TemplatesModal as the
 * primary path — the TemplatesModal is still reachable via the welcome's
 * "Browse more templates" link.
 */
export function useStartNewFlow() {
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const openWelcome = useFlowBuilderWelcomeStore((state) => state.open);
  // The button gives no sign of the create until the canvas opens, so a slow
  // answer invites a second click. That click would post another flow, and the
  // mutation then reports only the later request: a spare flow, or a "Name must
  // be unique" error while the first flow was created and never opened.
  const creating = useRef(false);

  return useCallback(async () => {
    if (creating.current) return;
    creating.current = true;
    try {
      const id = await addFlow();
      // Open BEFORE navigating so the canvas mounts with the welcome flag
      // already true — guarantees the overlay appears on the very first paint
      // instead of flashing the empty canvas then animating in.
      //
      // Tag the welcome with this flow's id so the mount can auto-close it if
      // the user navigates to a DIFFERENT flow (e.g. picks a template in the
      // TemplatesModal which spins up its own new flow).
      openWelcome(id);
      navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
    } finally {
      creating.current = false;
    }
  }, [addFlow, navigate, folderId, openWelcome]);
}
