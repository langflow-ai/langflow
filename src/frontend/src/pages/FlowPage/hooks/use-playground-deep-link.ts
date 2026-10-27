import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { getMessages } from "@/controllers/API/queries/messages/use-get-messages";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useSessionManagerStore } from "@/stores/sessionManagerStore";

type PlaygroundDeepLinkProps = {
  routeFlowId?: string;
  flowId?: string;
  hasChat: boolean;
};

export default function usePlaygroundDeepLink({
  routeFlowId,
  flowId,
  hasChat,
}: PlaygroundDeepLinkProps): void {
  const [searchParams] = useSearchParams();
  const requested = searchParams.get("playground") === "true";
  const sessionId = searchParams.get("session") || undefined;
  const setOpen = usePlaygroundStore((state) => state.setIsOpen);
  const setFullscreen = usePlaygroundStore((state) => state.setIsFullscreen);
  const activeRequest = useRef<{
    flowId: string;
    sessionId?: string;
    cancelled: boolean;
  } | null>(null);
  const mounted = useRef(true);

  // Keep the request alive through Strict Mode effect replay, but never apply
  // its response after this route has unmounted.
  useEffect(() => {
    mounted.current = true;
    // Remember intervening user actions even if the panel is reopened or the
    // selection returns to its original value before the lookup finishes.
    const unsubscribeSession = useSessionManagerStore.subscribe(
      (state, previous) => {
        if (
          activeRequest.current &&
          (state.flowId !== previous.flowId ||
            state.activeSessionId !== previous.activeSessionId)
        ) {
          activeRequest.current.cancelled = true;
        }
      },
    );
    const unsubscribePlayground = usePlaygroundStore.subscribe((state) => {
      if (activeRequest.current && !state.isOpen) {
        activeRequest.current.cancelled = true;
      }
    });
    return () => {
      mounted.current = false;
      unsubscribeSession();
      unsubscribePlayground();
    };
  }, []);

  useEffect(() => {
    if (!requested || !flowId || flowId !== routeFlowId || !hasChat) {
      activeRequest.current = null;
      return;
    }
    if (
      activeRequest.current?.flowId === flowId &&
      activeRequest.current.sessionId === sessionId
    ) {
      return;
    }
    const store = useSessionManagerStore.getState();
    store.initialize(flowId);
    setOpen(true);
    setFullscreen(true);
    const request = { flowId, sessionId, cancelled: false };
    activeRequest.current = request;

    if (!sessionId) return;
    if (sessionId === flowId) {
      store.setActiveSessionId(flowId);
      return;
    }
    const initialSessionId = useSessionManagerStore.getState().activeSessionId;

    // A linked session can be older than every loaded page. Check existence
    // within this flow without downloading all sessions or message history.
    void getMessages(flowId, { session_id: sessionId, limit: 1 })
      .then(({ data }) => {
        const current = useSessionManagerStore.getState();
        if (
          !mounted.current ||
          activeRequest.current !== request ||
          request.cancelled ||
          current.flowId !== flowId ||
          current.activeSessionId !== initialSessionId ||
          !usePlaygroundStore.getState().isOpen ||
          data.length === 0
        ) {
          return;
        }
        current.addSession({ id: sessionId, isLocal: false });
        current.setActiveSessionId(sessionId);
      })
      .catch(() => {
        // An unavailable or inaccessible session leaves the normal Playground
        // selection intact; opening a link must not create an empty session.
      });
  }, [
    requested,
    sessionId,
    routeFlowId,
    flowId,
    hasChat,
    setOpen,
    setFullscreen,
  ]);
}
