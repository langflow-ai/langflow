import { Button } from "@/components/ui/button";
import { createApiKey } from "@/controllers/API";
import { useState } from "react";
import { CopyInput } from "./copyInput";

export function ApiKeyGenerator({ flowName }: { flowName: string }) {
  const [isGeneratingApiKey, setIsGeneratingApiKey] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const generateApiKey = () => {
    setIsGeneratingApiKey(true);
    createApiKey(`MCP Server ${flowName}`)
      .then((res) => {
        setApiKey(res["api_key"]);
      })
      .catch((err) => {})
      .finally(() => {
        setIsGeneratingApiKey(false);
      });
  };
  return (
    <div className="flex w-full flex-col rounded-lg border p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">API Key</span>
        {!apiKey && (
          <Button
            size="sm"
            onClick={generateApiKey}
            loading={isGeneratingApiKey}
          >
            <span>Create API Key</span>
          </Button>
        )}
      </div>
      {apiKey && (
        <div className="mt-2 flex flex-col gap-2.5">
          <CopyInput value={apiKey} copyButton />
          <p className="text-xs text-muted-foreground">
            Save this key securely. You won't be able to view it again, and
            anyone with it can make requests on your behalf.
          </p>
        </div>
      )}
    </div>
  );
}
