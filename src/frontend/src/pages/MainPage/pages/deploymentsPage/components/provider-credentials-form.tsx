import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import type { ProviderCredentials } from "../types";

interface ProviderCredentialsFormProps {
  credentials: ProviderCredentials;
  onCredentialsChange: (credentials: ProviderCredentials) => void;
  layout?: "single-column" | "two-column";
  apiKeyRequired?: boolean;
  urlRequired?: boolean;
  urlReadOnly?: boolean;
  apiKeyPlaceholder?: string;
}

export default function ProviderCredentialsForm({
  credentials,
  onCredentialsChange,
  layout = "single-column",
  apiKeyRequired = true,
  urlRequired = true,
  urlReadOnly = false,
  apiKeyPlaceholder,
}: ProviderCredentialsFormProps) {
  const { t } = useTranslation();
  const [showApiKey, setShowApiKey] = useState(false);

  const urlAndApiKeyFields = (
    <>
      <div className="flex flex-col">
        <span className="pb-2 text-sm font-medium">
          {t("deployments.fieldServiceInstanceUrl")}{" "}
          {urlRequired ? <span className="text-destructive">*</span> : null}
        </span>
        <Input
          type="url"
          placeholder={t("deployments.placeholderApiUrl")}
          className="bg-muted"
          value={credentials.url}
          disabled={urlReadOnly}
          readOnly={urlReadOnly}
          onChange={(e) =>
            onCredentialsChange({
              ...credentials,
              url: e.target.value,
            })
          }
        />
      </div>
      <div className="flex flex-col">
        <span className="pb-2 text-sm font-medium">
          {t("deployments.fieldApiKey")}{" "}
          {apiKeyRequired ? (
            <span className="text-destructive">*</span>
          ) : (
            <span className="text-muted-foreground">
              ({t("deployments.optional")})
            </span>
          )}
        </span>
        <div className="relative">
          <Input
            type={showApiKey ? "text" : "password"}
            placeholder={
              apiKeyPlaceholder ?? t("deployments.placeholderApiKey")
            }
            className="bg-muted pr-10"
            value={credentials.api_key}
            onChange={(e) =>
              onCredentialsChange({
                ...credentials,
                api_key: e.target.value,
              })
            }
          />
          <button
            type="button"
            aria-label={
              showApiKey
                ? t("deployments.hideApiKey")
                : t("deployments.showApiKey")
            }
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setShowApiKey((prev) => !prev)}
          >
            <ForwardedIconComponent
              name={showApiKey ? "EyeOff" : "Eye"}
              className="h-4 w-4"
            />
          </button>
        </div>
        {!apiKeyRequired && (
          <span className="pt-2 text-xs text-muted-foreground">
            {t("deployments.leaveBlankCredential")}
          </span>
        )}
      </div>
    </>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col">
        <span className="pb-2 text-sm font-medium">
          {t("deployments.fieldName")}{" "}
          <span className="text-destructive">*</span>
        </span>
        <Input
          type="text"
          placeholder={t("deployments.placeholderEnvironmentName")}
          className="bg-muted"
          value={credentials.name}
          onChange={(e) =>
            onCredentialsChange({
              ...credentials,
              name: e.target.value,
            })
          }
        />
      </div>
      {layout === "two-column" ? (
        <div className="grid grid-cols-2 gap-4">{urlAndApiKeyFields}</div>
      ) : (
        urlAndApiKeyFields
      )}
    </div>
  );
}
