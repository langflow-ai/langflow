import { CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useGetVariablesByCategory } from "@/controllers/API/queries/variables/use-get-variables-by-category";
import { usePatchGlobalVariables } from "@/controllers/API/queries/variables/use-patch-global-variables";
import { usePostGlobalVariables } from "@/controllers/API/queries/variables/use-post-global-variables";
import useAlertStore from "@/stores/alertStore";

interface VariableData {
  id: string;
  name: string;
  value: string;
  type: string;
  category: string;
}

export default function KBSettingsPage() {
  const [isSaving, setIsSaving] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { variables, isLoading, refetch } = useGetVariablesByCategory("KB");
  const [variableMap, setVariableMap] = useState<Record<string, VariableData>>(
    {},
  );

  // Form state
  const [provider, setProvider] = useState("chroma");
  const [chromaHost, setChromaHost] = useState("localhost");
  const [chromaPort, setChromaPort] = useState("8000");
  const [chromaSslEnabled, setChromaSslEnabled] = useState(false);
  const [opensearchUrl, setOpensearchUrl] = useState("https://localhost:9200");
  const [opensearchIndexPrefix, setOpensearchIndexPrefix] =
    useState("langflow-");
  const [opensearchUsername, setOpensearchUsername] = useState("");
  const [opensearchPassword, setOpensearchPassword] = useState("");
  const [opensearchVerifyCerts, setOpensearchVerifyCerts] = useState(false);

  // Get mutation hooks
  const { mutateAsync: patchVariable } = usePatchGlobalVariables();
  const { mutateAsync: createVariable } = usePostGlobalVariables();

  // Load KB settings from the API
  useEffect(() => {
    if (variables) {
      // Process the response to extract KB settings
      const settings: Record<string, string | boolean> = {};
      const varMap: Record<string, VariableData> = {};

      variables.forEach((variable: any) => {
        if (variable.name) {
          // Handle boolean values
          let value = variable.value;
          if (
            variable.name.includes("ssl_enabled") ||
            variable.name.includes("verify_certs")
          ) {
            value = value === "true" || value === true;
          }

          settings[variable.name] = value || "";
          varMap[variable.name] = variable;
        }
      });

      setVariableMap(varMap);

      // Update state with retrieved settings
      setProvider((settings.kb_provider as string) || "chroma");
      setChromaHost((settings.kb_chroma_server_host as string) || "localhost");
      setChromaPort((settings.kb_chroma_server_http_port as string) || "8000");
      setChromaSslEnabled(
        (settings.kb_chroma_server_ssl_enabled as boolean) || false,
      );
      setOpensearchUrl(
        (settings.kb_opensearch_url as string) || "https://localhost:9200",
      );
      setOpensearchIndexPrefix(
        (settings.kb_opensearch_index_prefix as string) || "langflow-",
      );
      setOpensearchUsername((settings.kb_opensearch_username as string) || "");
      setOpensearchPassword((settings.kb_opensearch_password as string) || "");
      setOpensearchVerifyCerts(
        (settings.kb_opensearch_verify_certs as boolean) || false,
      );
    }
  }, [variables]);

  // Handle form submission
  const onSubmit = async () => {
    setIsSaving(true);
    try {
      const variablesToUpdate = [{ name: "kb_provider", value: provider }];

      // Add provider-specific variables
      if (provider === "chroma") {
        variablesToUpdate.push(
          { name: "kb_chroma_server_host", value: chromaHost },
          { name: "kb_chroma_server_http_port", value: chromaPort },
          {
            name: "kb_chroma_server_ssl_enabled",
            value: chromaSslEnabled.toString(),
          },
        );
      } else if (provider === "opensearch") {
        variablesToUpdate.push(
          { name: "kb_opensearch_url", value: opensearchUrl },
          { name: "kb_opensearch_index_prefix", value: opensearchIndexPrefix },
          { name: "kb_opensearch_username", value: opensearchUsername },
          { name: "kb_opensearch_password", value: opensearchPassword },
          {
            name: "kb_opensearch_verify_certs",
            value: opensearchVerifyCerts.toString(),
          },
        );
      }

      // Update or create variables
      for (const variable of variablesToUpdate) {
        const existingVariable = variableMap[variable.name];

        if (existingVariable) {
          // Update existing variable
          await patchVariable({
            id: existingVariable.id,
            name: variable.name,
            value: variable.value,
          });
        } else {
          // Create new variable
          await createVariable({
            name: variable.name,
            value: variable.value,
            type: "str",
            category: "KB",
          });
        }
      }

      setSuccessData({
        title: "Knowledge Base settings have been updated successfully",
      });

      // Refetch to get updated data
      await refetch();
    } catch (error) {
      console.error("Error saving KB settings:", error);
      setErrorData({
        title: "Failed to save Knowledge Base settings. Please try again.",
      });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6">
      <Card>
        <CardHeader>
          <CardTitle>Knowledge Base</CardTitle>
          <CardDescription>
            Configure the vector store settings for your Knowledge Bases.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="provider">Vector Store Provider</Label>
              <Select value={provider} onValueChange={setProvider}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="chroma">Chroma</SelectItem>
                  <SelectItem value="opensearch">OpenSearch</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                The vector store provider to use for Knowledge Bases.
              </p>
            </div>

            {/* Chroma Settings */}
            {provider === "chroma" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="chroma-host">Chroma Server Host</Label>
                  <Input
                    id="chroma-host"
                    placeholder="localhost"
                    value={chromaHost}
                    onChange={(e) => setChromaHost(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    The hostname or IP address of your Chroma server.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="chroma-port">Chroma Server Port</Label>
                  <Input
                    id="chroma-port"
                    placeholder="8000"
                    value={chromaPort}
                    onChange={(e) => setChromaPort(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    The HTTP port for your Chroma server.
                  </p>
                </div>

                <div className="flex flex-row items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <Label className="text-base">SSL Enabled</Label>
                    <p className="text-sm text-muted-foreground">
                      Enable SSL/TLS for secure connections to Chroma server.
                    </p>
                  </div>
                  <Switch
                    checked={chromaSslEnabled}
                    onCheckedChange={setChromaSslEnabled}
                  />
                </div>
              </>
            )}

            {/* OpenSearch Settings */}
            {provider === "opensearch" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="opensearch-url">OpenSearch URL</Label>
                  <Input
                    id="opensearch-url"
                    placeholder="https://localhost:9200"
                    value={opensearchUrl}
                    onChange={(e) => setOpensearchUrl(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    The full URL to your OpenSearch cluster.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="opensearch-prefix">Index Prefix</Label>
                  <Input
                    id="opensearch-prefix"
                    placeholder="langflow-"
                    value={opensearchIndexPrefix}
                    onChange={(e) => setOpensearchIndexPrefix(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    Prefix for OpenSearch indices created by Langflow.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="opensearch-username">Username</Label>
                  <Input
                    id="opensearch-username"
                    placeholder="admin"
                    value={opensearchUsername}
                    onChange={(e) => setOpensearchUsername(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    Username for OpenSearch authentication (optional).
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="opensearch-password">Password</Label>
                  <Input
                    id="opensearch-password"
                    type="password"
                    placeholder="••••••••"
                    value={opensearchPassword}
                    onChange={(e) => setOpensearchPassword(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    Password for OpenSearch authentication (optional).
                  </p>
                </div>

                <div className="flex flex-row items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <Label className="text-base">Verify SSL Certificates</Label>
                    <p className="text-sm text-muted-foreground">
                      Verify SSL certificates when connecting to OpenSearch.
                    </p>
                  </div>
                  <Switch
                    checked={opensearchVerifyCerts}
                    onCheckedChange={setOpensearchVerifyCerts}
                  />
                </div>
              </>
            )}

            <Button onClick={onSubmit} disabled={isSaving}>
              {isSaving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Save Settings
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
