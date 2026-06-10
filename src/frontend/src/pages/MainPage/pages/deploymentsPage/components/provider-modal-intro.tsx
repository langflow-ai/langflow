import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { decorateWxoUrl } from "@/utils/decorate-wxo-url";
import type { ProviderAccount } from "../types";

interface ProviderModalIntroProps {
  provider?: ProviderAccount | null;
}

export default function ProviderModalIntro({
  provider,
}: ProviderModalIntroProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3 rounded-lg border border-border bg-muted p-3">
        <ForwardedIconComponent
          name="WatsonxOrchestrate"
          className="h-8 w-8 text-foreground"
        />
        <span className="text-sm font-medium">watsonx Orchestrate</span>
        <Badge variant="purpleStatic" size="xq" className="shrink-0">
          {t("sidebar.betaLabel")}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        {provider ? (
          t("deployments.updateEnvironmentCredentials")
        ) : (
          <>
            {t("deployments.wxoConfigureCredentials")}{" "}
            <a
              href={decorateWxoUrl(
                "https://www.ibm.com/products/watsonx-orchestrate#pricing",
                "signup-pricing",
              )}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-primary hover:underline"
            >
              {t("deployments.wxoSignUp")}
            </a>
            {t("deployments.wxoAlreadyHaveAccountConnector")}{" "}
            <a
              href={decorateWxoUrl(
                "https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=api-getting-started",
                "docs-credentials",
              )}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-primary hover:underline"
            >
              {t("deployments.wxoFindCredentials")}
            </a>
            {t("deployments.sentenceEnd")}
          </>
        )}
      </p>
    </div>
  );
}
