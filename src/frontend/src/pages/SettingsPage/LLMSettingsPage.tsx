import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useGetVariablesByCategory } from "@/controllers/API/queries/variables/use-get-variables-by-category";
import { usePatchGlobalVariables } from "@/controllers/API/queries/variables/use-patch-global-variables";
import { usePostGlobalVariables } from "@/controllers/API/queries/variables/use-post-global-variables";

import useAlertStore from "@/stores/alertStore";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

interface LLMSettingsFormValues {
  provider: string;
  model: string;
  base_url: string;
  api_key: string;
}

interface VariableData {
  id: string;
  name: string;
  value: string;
  type: string;
  category: string;
}

export default function LLMSettingsPage() {
  const [isSaving, setIsSaving] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { variables, isLoading, refetch } = useGetVariablesByCategory("LLM");
  const [variableMap, setVariableMap] = useState<Record<string, VariableData>>(
    {},
  );

  // Get mutation hooks
  const { mutateAsync: patchVariable } = usePatchGlobalVariables();
  const { mutateAsync: createVariable } = usePostGlobalVariables();

  const form = useForm<LLMSettingsFormValues>({
    defaultValues: {
      provider: "openai",
      model: "gpt-4o",
      base_url: "https://api.openai.com/v1",
      api_key: "",
    },
  });

  // Load LLM settings from the API
  useEffect(() => {
    if (variables) {
      // Process the response to extract LLM settings
      const settings: Record<string, string> = {};
      const varMap: Record<string, VariableData> = {};

      variables.forEach((variable: any) => {
        if (variable.name) {
          settings[variable.name] = variable.value || "";
          varMap[variable.name] = variable;
        }
      });

      setVariableMap(varMap);

      // Update form with retrieved settings
      form.reset({
        provider: settings.provider || "openai",
        model: settings.model || "gpt-4o",
        base_url: settings.base_url || "https://api.openai.com/v1",
        api_key: settings.api_key || "",
      });
    }
  }, [variables, form]);

  // Handle form submission
  const onSubmit = async (data: LLMSettingsFormValues) => {
    try {
      setIsSaving(true);

      // Process each setting
      const savePromises = Object.entries(data).map(async ([key, value]) => {
        // For API key, if it's empty and there's an existing value, skip updating it
        if (key === "api_key" && value === "" && variableMap.api_key) {
          return Promise.resolve();
        }

        // Skip empty values except for base_url which can be empty
        if (value === "" && key !== "base_url") return Promise.resolve();

        const existingVariable = variableMap[key];

        if (existingVariable) {
          // Update existing variable using the patch hook
          return patchVariable({
            id: existingVariable.id,
            value: value,
            name: key,
          });
        } else {
          // Create new variable using the post hook
          return createVariable({
            name: key,
            value: value,
            type: key === "api_key" ? "Credential" : "Generic",
            category: "LLM",
          });
        }
      });

      await Promise.all(savePromises);

      // Refresh the variables list
      await refetch();

      setSuccessData({ title: "LLM settings saved successfully" });
    } catch (error) {
      console.error("Failed to save LLM settings:", error);
      setErrorData({
        title: "Failed to save LLM settings",
        list: [(error as Error)?.message || "Unknown error"],
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Get available models based on selected provider
  const getModelsForProvider = (provider: string) => {
    switch (provider) {
      case "openai":
        return [
          { value: "gpt-4o", label: "GPT-4o" },
          { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
          { value: "gpt-4", label: "GPT-4" },
          { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
        ];
      case "anthropic":
        return [
          { value: "claude-3-opus", label: "Claude 3 Opus" },
          { value: "claude-3-sonnet", label: "Claude 3 Sonnet" },
          { value: "claude-3-haiku", label: "Claude 3 Haiku" },
        ];
      default:
        return [];
    }
  };

  // Update base URL when provider changes
  const handleProviderChange = (value: string) => {
    form.setValue("provider", value);

    // Set default base URL based on provider
    if (value === "openai") {
      form.setValue("base_url", "https://api.openai.com/v1");
    } else if (value === "anthropic") {
      form.setValue("base_url", "");
    }

    // Reset model to first available for the selected provider
    const models = getModelsForProvider(value);
    if (models.length > 0) {
      form.setValue("model", models[0].value);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6">
      <Card>
        <CardHeader>
          <CardTitle>LLM Settings</CardTitle>
          <CardDescription>
            Configure the Large Language Model settings for your application.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="space-y-6"
              autoComplete="off"
            >
              <FormField
                control={form.control}
                name="provider"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Provider</FormLabel>
                    <Select
                      onValueChange={(value) => handleProviderChange(value)}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a provider" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="anthropic">Anthropic</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      The AI provider to use for language model services.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="model"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Model</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a model" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {getModelsForProvider(form.getValues("provider")).map(
                          (model) => (
                            <SelectItem key={model.value} value={model.value}>
                              {model.label}
                            </SelectItem>
                          ),
                        )}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      The specific model to use for generating responses.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="base_url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Base URL (Optional)</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="https://api.openai.com/v1"
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>
                      The base URL for API requests. Leave default for standard
                      services.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="api_key"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center gap-2">
                      API Key
                      {variableMap.api_key && (
                        <span className="flex items-center text-xs font-normal text-green-600">
                          <CheckCircle2 className="mr-1 h-3 w-3" />
                          Key exists
                        </span>
                      )}
                    </FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Input
                          type="password"
                          placeholder={
                            variableMap.api_key
                              ? "••••••••••••••••••••••••••"
                              : "Enter your API key"
                          }
                          autoComplete="off"
                          {...field}
                        />
                        {variableMap.api_key && field.value === "" && (
                          <div className="absolute inset-y-0 right-0 flex items-center pr-3 text-sm text-muted-foreground">
                            Leave empty to keep existing key
                          </div>
                        )}
                      </div>
                    </FormControl>
                    <FormDescription>
                      Your API key for authentication with the provider.
                      {variableMap.api_key && field.value === "" && (
                        <span className="mt-1 block text-green-600">
                          An API key is already saved. Enter a new value to
                          update it.
                        </span>
                      )}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button type="submit" disabled={isSaving}>
                {isSaving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  "Save Settings"
                )}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
