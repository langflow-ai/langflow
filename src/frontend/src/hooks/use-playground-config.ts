import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";

/**
 * Hook to get the config for playground pages.
 * The /config endpoint automatically returns the appropriate response based on auth status:
 * - Authenticated users: Full ConfigResponse
 * - Unauthenticated users: PublicConfigResponse (limited fields)
 */
export const usePlaygroundConfig = () => {
  const { data: config } = useGetConfig({});
  return config;
};
