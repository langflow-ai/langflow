import { useGetTritonServers } from "@/controllers/API/queries/triton/use-get-triton-servers";
import type { TritonServerType } from "@/types/triton";

export function useTritonConnection(serverId: string | undefined): {
  server: TritonServerType | undefined;
  isLoading: boolean;
} {
  const { data: servers, isLoading } = useGetTritonServers();
  const server = servers?.find((s) => s.id === serverId);
  return { server, isLoading };
}
