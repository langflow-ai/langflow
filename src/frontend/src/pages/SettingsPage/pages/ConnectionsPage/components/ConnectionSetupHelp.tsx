import { useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import {
  connectionSetupGuide,
  suggestedCallbackUrl,
} from "../helpers/setup-guide";

export default function ConnectionSetupHelp({
  providerId,
  noRegistration,
  usesToken = false,
  docsUrl,
}: {
  providerId: string;
  noRegistration: boolean;
  usesToken?: boolean;
  docsUrl?: string | null;
}) {
  const { t } = useTranslation();
  const [copyState, setCopyState] = useState<"copied" | "failed" | null>(null);
  const guide = connectionSetupGuide(providerId, usesToken, docsUrl);
  const { host, protocol } = customGetHostProtocol();
  const callbackUrl = suggestedCallbackUrl(providerId, `${protocol}//${host}`);
  const needsSetup = noRegistration && !usesToken;

  const copyCallback = async () => {
    if (!callbackUrl) return;
    try {
      await navigator.clipboard.writeText(callbackUrl);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  };

  if (!guide && !needsSetup) return null;

  return (
    <div className="space-y-2 text-xs" data-testid="connection-setup-help">
      {needsSetup && (
        <p className="text-destructive" role="alert">
          {t("connections.add.noRegistration")}
        </p>
      )}
      {guide && (
        <a
          href={guide}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-primary underline"
          data-testid="connection-setup-guide"
        >
          {t("connections.add.setupGuide")}
          <IconComponent name="ExternalLink" className="h-3 w-3" />
        </a>
      )}
      {needsSetup && guide && (
        <div className="space-y-2 rounded-md border border-border bg-muted p-3">
          <p className="break-words">
            {t("connections.add.operatorSetup", {
              variable: "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS",
            })}
          </p>
          {callbackUrl ? (
            <>
              <p className="font-medium">
                {t("connections.add.callbackLabel")}
              </p>
              <code
                className="block select-text break-all"
                data-testid="connection-callback-url"
              >
                {callbackUrl}
              </code>
              <p className="text-muted-foreground">
                {t("connections.add.callbackHelp")}
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                ignoreTitleCase
                onClick={copyCallback}
                data-testid="connection-copy-callback"
              >
                {t("connections.add.copyCallback")}
              </Button>
              <p role="status">
                {copyState === "copied"
                  ? t("connections.add.callbackCopied")
                  : copyState === "failed"
                    ? t("connections.add.callbackCopyFailed")
                    : null}
              </p>
            </>
          ) : (
            <p>{t("connections.add.callbackUnavailable")}</p>
          )}
        </div>
      )}
    </div>
  );
}
