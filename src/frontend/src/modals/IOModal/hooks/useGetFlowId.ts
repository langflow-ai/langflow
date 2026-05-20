import { v5 as uuidv5 } from "uuid";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";

export const useGetFlowId = () => {
  const clientId = useUtilityStore((state) => state.clientId);
  const realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const playgroundPage = useFlowStore((state) => state.playgroundPage);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const userData = useAuthStore((state) => state.userData);

  if (!playgroundPage) return realFlowId;

  // Authenticated users on playground: use user_id for deterministic UUID
  // This matches the backend's UUID v5 generation for logged-in users.
  // Use `autoLogin === false` (not `!autoLogin`) to avoid race condition
  // when autoLogin is still null (unresolved) — treat null same as true.
  if (isAuthenticated && autoLogin === false && userData?.id) {
    return uuidv5(`${userData.id}_${realFlowId}`, uuidv5.DNS);
  }

  // Anonymous/auto-login users: use client_id (original behavior)
  return uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS);
};
