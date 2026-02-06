import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import { useGetPublicConfig } from "@/controllers/API/queries/config/use-get-public-config";

/**
 * Hook to get the appropriate config based on whether we're on a playground page.
 * Uses public config for playground pages (unauthenticated), otherwise uses authenticated config.
 */
export const usePlaygroundConfig = (playgroundPage: boolean) => {
  const { data: authConfig } = useGetConfig({ enabled: !playgroundPage });
  const { data: publicConfig } = useGetPublicConfig({ enabled: playgroundPage });
  return playgroundPage ? publicConfig : authConfig;
};
