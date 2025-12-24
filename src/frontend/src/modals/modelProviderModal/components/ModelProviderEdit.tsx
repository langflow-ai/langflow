import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { PROVIDER_VARIABLE_MAPPING } from "@/constants/providerConstants";

export interface ModelProviderEditProps {
  authName: string;
  onAuthNameChange: (value: string) => void;
  apiKey: string;
  onApiKeyChange: (value: string) => void;
  apiBase: string;
  onApiBaseChange: (value: string) => void;
  providerName?: string;
}

/**
 * Form for configuring provider credentials (API key, base URL).
 * Used when setting up a new provider or updating existing credentials.
 */
const ModelProviderEdit = ({
  authName,
  onAuthNameChange,
  apiKey,
  onApiKeyChange,
  apiBase,
  onApiBaseChange,
  providerName, // Reserved for future provider-specific behavior
}: ModelProviderEditProps) => {
  return (
    <div className="flex flex-col gap-4 p-4" data-testid="model-provider-edit">
      <div className="text-[13px] -mb-1 font-medium flex items-center gap-1">
        Authorization Name
        <ForwardedIconComponent
          name="info"
          className="w-4 h-4 text-muted-foreground ml-1"
        />
      </div>
      <Input
        placeholder="Authorization Name"
        value={
          providerName
            ? PROVIDER_VARIABLE_MAPPING[providerName]
            : "UNKNOWN_API_KEY"
        }
        disabled
        onChange={(e) => onAuthNameChange(e.target.value)}
        data-testid="auth-name-input"
      />
      <div className="text-[13px] -mb-1 font-medium flex items-center gap-1">
        API Key <span className="text-red-500">*</span>
        <ForwardedIconComponent
          name="info"
          className="w-4 h-4 text-muted-foreground ml-1"
        />
      </div>
      <Input
        placeholder="Enter your API key"
        type="password"
        value={apiKey}
        required
        onChange={(e) => onApiKeyChange(e.target.value)}
        data-testid="api-key-input"
      />
      <div className="text-muted-foreground text-xs flex items-center gap-1 -mt-1 hover:underline cursor-pointer w-fit">
        Find your API key{" "}
        <ForwardedIconComponent name="external-link" className="w-4 h-4" />
      </div>
      <div className="text-[13px] -mb-1 font-medium flex items-center gap-1">
        API Base
        <ForwardedIconComponent
          name="info"
          className="w-4 h-4 text-muted-foreground ml-1"
        />{" "}
      </div>
      <Input
        placeholder="API Base URL (optional)"
        value={apiBase}
        onChange={(e) => onApiBaseChange(e.target.value)}
        data-testid="api-base-input"
      />
    </div>
  );
};

export default ModelProviderEdit;
