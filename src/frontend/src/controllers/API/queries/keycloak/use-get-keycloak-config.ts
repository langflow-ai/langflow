import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

interface KeycloakConfig {
  enabled: boolean;
  button_text: string;
}

async function getKeycloakConfig(): Promise<KeycloakConfig> {
  const response = await api.get<KeycloakConfig>("/api/v1/keycloak/config");
  return response.data;
}

export function useGetKeycloakConfig() {
  return useQuery({
    queryKey: ["keycloakConfig"],
    queryFn: getKeycloakConfig,
    staleTime: Infinity,
    retry: false,
    // Treat a failed request (plugin not installed) as "disabled"
    // so the button is simply not shown rather than causing an error.
  });
}
