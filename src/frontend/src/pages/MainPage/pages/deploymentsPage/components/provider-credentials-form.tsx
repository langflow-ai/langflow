import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
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
  const [showApiKey, setShowApiKey] = useState(false);

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
        <div className="relative">
          <Input
            type={showApiKey ? "text" : "password"}
            placeholder="Enter your API key"
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
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setShowApiKey((prev) => !prev)}
            tabIndex={-1}
          >
            <ForwardedIconComponent
              name={showApiKey ? "EyeOff" : "Eye"}
              className="h-4 w-4"
            />
          </button>
        </div>
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
