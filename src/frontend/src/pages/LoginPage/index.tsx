import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import { useGetKeycloakConfig } from "@/controllers/API/queries/keycloak/use-get-keycloak-config";
import { useSanitizeRedirectUrl } from "@/hooks/use-sanitize-redirect-url";
import { Button } from "../../components/ui/button";

export default function LoginPage(): JSX.Element {
  useSanitizeRedirectUrl();

  const { data: keycloakConfig } = useGetKeycloakConfig();

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center bg-muted">
      <div className="flex w-72 flex-col items-center justify-center gap-2">
        <LangflowLogo
          title="Langflow logo"
          className="mb-4 h-10 w-10 scale-[1.5]"
        />
        <span className="mb-6 text-2xl font-semibold text-primary">
          Sign in to Langflow
        </span>
        <div className="w-full">
          <Button
            className="w-full"
            variant="default"
            type="button"
            disabled={!keycloakConfig?.enabled}
            ignoreTitleCase
            onClick={() => {
              window.location.href = "/api/v1/keycloak/login";
            }}
          >
            SK하이닉스 SSO 로그인
          </Button>
        </div>
      </div>
    </div>
  );
}
