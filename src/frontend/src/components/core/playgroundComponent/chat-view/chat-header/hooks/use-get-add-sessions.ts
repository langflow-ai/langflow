import { useMemo } from "react";
import { NEW_SESSION_NAME } from "@/constants/constants";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";

interface UseGetAddSessionsProps {
  flowId?: string;
}

type UseGetAddSessionsReturnType = (props: UseGetAddSessionsProps) => {
  addNewSession: (() => string) | undefined;
  sessions: string[];
};

export const useGetAddSessions: UseGetAddSessionsReturnType = ({ flowId }) => {
  const { data: dbSessionsResponse } = useGetSessionsFromFlowQuery({
    id: flowId,
  });
  const sessions = dbSessionsResponse?.sessions ?? [];

  const addNewSession: (() => string) | undefined = () => {
    const newSessionId = `${NEW_SESSION_NAME} ${sessions.length}`;
    return newSessionId;
  };

  const stableSessions = useMemo(() => [...sessions], [sessions]);

  return {
    addNewSession,
    sessions: stableSessions,
  };
};
