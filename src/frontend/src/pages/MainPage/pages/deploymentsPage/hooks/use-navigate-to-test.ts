import { useCallback } from "react";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

export function useNavigateToTest() {
  const navigate = useCustomNavigate();
  return useCallback(
    (deployment: { id: string; name: string }, providerId: string) => {
      navigate("/all", {
        state: {
          flowType: "deployments",
          testDeployment: deployment,
          testProviderId: providerId,
        },
      });
    },
    [navigate],
  );
}
