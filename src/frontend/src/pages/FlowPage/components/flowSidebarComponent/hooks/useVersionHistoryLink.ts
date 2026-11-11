import { useCallback, useEffect, useRef } from "react";
import { useLocation, useParams, useSearchParams } from "react-router-dom";
import { useSidebar } from "@/components/ui/sidebar";

/** Hand a version link to the existing preview once its flow has loaded. */
export function useVersionHistoryLink(
  currentFlowId: string | undefined,
  enabled: boolean,
) {
  const { id } = useParams();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const { setOpen, setActiveSection } = useSidebar();
  const requestedVersionId =
    enabled && id === currentFlowId
      ? params.get("version") || undefined
      : undefined;
  const requestKey = requestedVersionId
    ? `${id}:${requestedVersionId}:${location.key}`
    : undefined;
  const latestRequest = useRef(requestKey);
  latestRequest.current = requestKey;
  const openedRequest = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!requestKey || openedRequest.current === requestKey) return;
    openedRequest.current = requestKey;
    setActiveSection("versions");
    setOpen(true);
  }, [requestKey, setActiveSection, setOpen]);

  const consumeVersionLink = useCallback(() => {
    // An old preview finishing must not replace a newer route or query.
    if (!requestKey || latestRequest.current !== requestKey) return;
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.delete("version");
        return next;
      },
      { replace: true },
    );
  }, [requestKey, setParams]);

  return { requestedVersionId, consumeVersionLink };
}
