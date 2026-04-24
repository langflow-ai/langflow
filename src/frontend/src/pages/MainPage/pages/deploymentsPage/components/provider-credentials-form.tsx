import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { Input } from "@/components/ui/input";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import type { ProviderCredentials } from "../types";

interface ProviderCredentialsFormProps {
  credentials: ProviderCredentials;
  onCredentialsChange: (credentials: ProviderCredentials) => void;
  layout?: "single-column" | "two-column";
}

export default function ProviderCredentialsForm({
  credentials,
  onCredentialsChange,
  layout = "single-column",
}: ProviderCredentialsFormProps) {
  const { data: globalVariables } = useGetGlobalVariables();
  const globalVariableOptions = (globalVariables ?? []).map(
    (variable) => variable.name,
  );

  const urlAndApiKeyFields = (
    <>
      <div className="flex flex-col">
        <span className="pb-2 text-sm font-medium">
          Service Instance URL <span className="text-destructive">*</span>
        </span>
        <Input
          type="url"
          placeholder="https://api.example.com"
          className="bg-muted"
          value={credentials.url}
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
          API Key <span className="text-destructive">*</span>
        </span>
        <InputComponent
          nodeStyle
          password
          id="provider-api-key"
          placeholder="Enter your API key"
          value={credentials.api_key}
          options={globalVariableOptions}
          optionsPlaceholder="Global Variables"
          optionsIcon="Globe"
          selectedOption={
            credentials.api_key_source === "variable" ? credentials.api_key : "" // pragma: allowlist secret
          }
          setSelectedOption={(selected) =>
            onCredentialsChange({
              ...credentials,
              api_key: selected,
              api_key_source: selected === "" ? "raw" : "variable",
            })
          }
          onChange={(value) =>
            onCredentialsChange({
              ...credentials,
              api_key: value,
              api_key_source: "raw", // pragma: allowlist secret
            })
          }
        />
      </div>
    </>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col">
        <span className="pb-2 text-sm font-medium">
          Name <span className="text-destructive">*</span>
        </span>
        <Input
          type="text"
          placeholder="e.g. Production"
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
