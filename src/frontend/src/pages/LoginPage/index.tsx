import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import { useGetKeycloakConfig } from "@/controllers/API/queries/keycloak/use-get-keycloak-config";
import { useSanitizeRedirectUrl } from "@/hooks/use-sanitize-redirect-url";
import { useSearchParams } from "react-router-dom";
import { Button } from "../../components/ui/button";

const ERROR_MESSAGES: Record<string, string> = {
  unauthorized: "프로젝트 접근 권한이 없습니다. 관리자에게 문의하세요.",
  no_employee_id: "사번 정보를 확인할 수 없습니다. 관리자에게 문의하세요.",
  hcp_unavailable:
    "권한 확인 서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요.",
};

export default function LoginPage(): JSX.Element {
  useSanitizeRedirectUrl();

  const [searchParams] = useSearchParams();
  const errorCode = searchParams.get("error");
  const employeeId = searchParams.get("employee");

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
        {errorCode && (
          <div className="mb-4 w-full rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            <p>{ERROR_MESSAGES[errorCode] ?? `로그인 오류: ${errorCode}`}</p>
            {employeeId && (
              <p className="mt-1 text-xs text-red-500">
                사번: {employeeId}
              </p>
            )}
          </div>
        )}
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
            {keycloakConfig?.button_text ?? "SK하이닉스 SSO 로그인"}
          </Button>
        </div>
      </div>
    </div>
  );
}
