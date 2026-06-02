import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
} from "react";
import useAuthStore from "@/stores/authStore";
import type { CollaborationSelectionTarget } from "@/types/flow-collaboration";
import { setCollaborationLocalSelection } from "./collaboration-local-selection-store";
import {
  buildCollaborationSelectionIndexes,
  type CollaborationSelectionIndexes,
} from "./collaboration-selection-indexes";
import {
  type UseFlowCollaborationEditingReturn,
  useFlowCollaborationEditing,
} from "./use-flow-collaboration-editing";

type FlowCollaborationContextValue = UseFlowCollaborationEditingReturn & {
  selectionIndexes: CollaborationSelectionIndexes;
};

export type FlowCollaborationSelectionApi = {
  betaEnabled: boolean;
  isCollaborationReady: boolean;
  sendSelectionUpdate: (target: CollaborationSelectionTarget | null) => void;
};

const FlowCollaborationContext =
  createContext<FlowCollaborationContextValue | null>(null);

const FlowCollaborationSelectionApiContext =
  createContext<FlowCollaborationSelectionApi | null>(null);

export function FlowCollaborationProvider({
  flowId,
  children,
}: {
  flowId: string | undefined;
  children: ReactNode;
}): JSX.Element {
  const editing = useFlowCollaborationEditing({ flowId });
  const userData = useAuthStore((state) => state.userData);

  useEffect(() => {
    setCollaborationLocalSelection(null);
  }, [flowId]);

  useEffect(() => {
    if (!editing.betaEnabled) {
      setCollaborationLocalSelection(null);
    }
  }, [editing.betaEnabled]);

  const selectionIndexes = useMemo(
    () =>
      buildCollaborationSelectionIndexes({
        users: editing.users,
        selections: editing.selections,
        currentUserId: userData?.id,
        currentUserProfile: userData
          ? {
              user_id: userData.id,
              username: userData.username,
              profile_image: userData.profile_image,
            }
          : null,
      }),
    [
      editing.selections,
      editing.users,
      userData?.id,
      userData?.profile_image,
      userData?.username,
    ],
  );

  const value = useMemo(
    () => ({
      ...editing,
      selectionIndexes,
    }),
    [editing, selectionIndexes],
  );

  const selectionApi = useMemo(
    () => ({
      betaEnabled: editing.betaEnabled,
      isCollaborationReady: editing.isCollaborationReady,
      sendSelectionUpdate: editing.sendSelectionUpdate,
    }),
    [
      editing.betaEnabled,
      editing.isCollaborationReady,
      editing.sendSelectionUpdate,
    ],
  );

  return (
    <FlowCollaborationSelectionApiContext.Provider value={selectionApi}>
      <FlowCollaborationContext.Provider value={value}>
        {children}
      </FlowCollaborationContext.Provider>
    </FlowCollaborationSelectionApiContext.Provider>
  );
}

export function useFlowCollaborationContext(): FlowCollaborationContextValue {
  const value = useContext(FlowCollaborationContext);
  if (!value) {
    throw new Error(
      "useFlowCollaborationContext must be used within FlowCollaborationProvider",
    );
  }
  return value;
}

export function useOptionalFlowCollaborationContext(): FlowCollaborationContextValue | null {
  return useContext(FlowCollaborationContext);
}

export function useFlowCollaborationSelectionApi(): FlowCollaborationSelectionApi {
  const value = useContext(FlowCollaborationSelectionApiContext);
  if (!value) {
    throw new Error(
      "useFlowCollaborationSelectionApi must be used within FlowCollaborationProvider",
    );
  }
  return value;
}
