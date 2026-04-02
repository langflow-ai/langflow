import { useCallback, useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  useDeleteCustomProvider,
  useDiscoverModels,
  usePatchCustomProvider,
  usePostCustomProvider,
} from "@/controllers/API/queries/custom-providers";
import type {
  CustomProviderCreate,
  CustomProviderModelSchema,
  CustomProviderRead,
} from "@/types/custom-providers";
import useAlertStore from "@/stores/alertStore";

export interface CustomProviderFormProps {
  /** The existing provider to edit, or null when creating a new one */
  provider: CustomProviderRead | null;
  /** Called after a successful save or delete to reset selection */
  onDone: () => void;
}

/** Convert an array of model schemas to a newline-delimited string for the textarea */
const modelsToText = (
  models: Array<{ name: string; tool_calling?: boolean }>,
): string => {
  return models.map((m) => m.name).join("\n");
};

/** Convert newline-delimited text to model schema array */
const textToModels = (text: string): CustomProviderModelSchema[] => {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((name) => ({ name, tool_calling: false }));
};

const CustomProviderForm = ({ provider, onDone }: CustomProviderFormProps) => {
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [modelsText, setModelsText] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { mutateAsync: createProvider, isPending: isCreating } =
    usePostCustomProvider();
  const { mutateAsync: updateProvider, isPending: isUpdating } =
    usePatchCustomProvider();
  const { mutateAsync: deleteProvider, isPending: isDeleting } =
    useDeleteCustomProvider();

  const isEditing = provider !== null;

  // Discover models — only usable for existing providers
  const {
    refetch: discoverRefetch,
    isFetching: isDiscovering,
  } = useDiscoverModels(
    { providerId: provider?.id ?? "" },
    { enabled: false },
  );

  // Populate form when provider changes
  useEffect(() => {
    if (provider) {
      setName(provider.name);
      setBaseUrl(provider.base_url);
      setApiKey("");
      setModelsText(modelsToText(provider.models));
    } else {
      setName("");
      setBaseUrl("");
      setApiKey("");
      setModelsText("");
    }
    setShowDeleteConfirm(false);
  }, [provider]);

  const isSaving = isCreating || isUpdating;

  const canSave =
    name.trim() !== "" &&
    baseUrl.trim() !== "" &&
    (isEditing || apiKey.trim() !== "");

  const handleSave = useCallback(async () => {
    if (!canSave) return;

    try {
      if (isEditing && provider) {
        const body: Record<string, any> = {
          name: name.trim(),
          base_url: baseUrl.trim(),
          models: textToModels(modelsText),
        };
        if (apiKey.trim()) {
          body.api_key = apiKey.trim();
        }
        await updateProvider({ id: provider.id, body });
        setSuccessData({ title: `${name.trim()} updated` });
      } else {
        const payload: CustomProviderCreate = {
          name: name.trim(),
          base_url: baseUrl.trim(),
          api_key: apiKey.trim(),
          models: textToModels(modelsText),
        };
        await createProvider(payload);
        setSuccessData({ title: `${name.trim()} created` });
      }
      onDone();
    } catch (error: any) {
      setErrorData({
        title: isEditing ? "Error Updating Provider" : "Error Creating Provider",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unexpected error occurred.",
        ],
      });
    }
  }, [
    canSave,
    isEditing,
    provider,
    name,
    baseUrl,
    apiKey,
    modelsText,
    createProvider,
    updateProvider,
    setSuccessData,
    setErrorData,
    onDone,
  ]);

  const handleDelete = useCallback(async () => {
    if (!provider) return;
    try {
      await deleteProvider(provider.id);
      setSuccessData({ title: `${provider.name} deleted` });
      onDone();
    } catch (error: any) {
      setErrorData({
        title: "Error Deleting Provider",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unexpected error occurred.",
        ],
      });
    }
  }, [provider, deleteProvider, setSuccessData, setErrorData, onDone]);

  const handleDiscover = useCallback(async () => {
    if (!provider) return;
    try {
      const result = await discoverRefetch();
      const data = result.data;
      if (data && data.models && data.models.length > 0) {
        setModelsText(data.models.join("\n"));
        setSuccessData({
          title: `Discovered ${data.models.length} model${data.models.length === 1 ? "" : "s"}`,
        });
      } else if (data?.error) {
        setErrorData({
          title: "Discovery Failed",
          list: [data.error],
        });
      } else {
        setErrorData({
          title: "No Models Found",
          list: ["The provider did not return any models."],
        });
      }
    } catch (error: any) {
      setErrorData({
        title: "Discovery Failed",
        list: [
          error?.message || "Could not discover models from this provider.",
        ],
      });
    }
  }, [provider, discoverRefetch, setSuccessData, setErrorData]);

  return (
    <div className="flex flex-col gap-1 px-4 pt-4 overflow-y-auto">
      <div className="flex flex-row gap-1 min-w-[300px]">
        <span className="text-[13px] font-semibold mr-auto">
          {isEditing ? "Edit Custom Provider" : "New Custom Provider"}
        </span>
      </div>
      <span className="text-[13px] text-muted-foreground pt-1 pb-2">
        {isEditing
          ? "Update the provider configuration below"
          : "Add an OpenAI-compatible provider"}
      </span>

      <div className="flex flex-col gap-3">
        {/* Provider Name */}
        <div className="flex flex-col gap-1">
          <label className="text-[12px] font-medium text-muted-foreground">
            Provider Name
            <span className="text-destructive ml-1">*</span>
          </label>
          <Input
            placeholder="e.g. My Provider"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={isSaving}
          />
        </div>

        {/* Base URL */}
        <div className="flex flex-col gap-1">
          <label className="text-[12px] font-medium text-muted-foreground">
            Base URL
            <span className="text-destructive ml-1">*</span>
          </label>
          <Input
            placeholder="https://api.example.com/v1"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            disabled={isSaving}
          />
        </div>

        {/* API Key */}
        <div className="flex flex-col gap-1">
          <label className="text-[12px] font-medium text-muted-foreground">
            API Key
            {!isEditing && <span className="text-destructive ml-1">*</span>}
          </label>
          <Input
            placeholder={isEditing ? "••••••••" : "sk-..."}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            type="password"
            disabled={isSaving}
          />
          {isEditing && (
            <span className="text-[11px] text-muted-foreground">
              Leave blank to keep the existing key
            </span>
          )}
        </div>

        {/* Models */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <label className="text-[12px] font-medium text-muted-foreground">
              Models
            </label>
            {isEditing && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs px-2"
                onClick={handleDiscover}
                loading={isDiscovering}
                disabled={isDiscovering || isSaving}
              >
                <ForwardedIconComponent name="Search" className="h-3 w-3 mr-1" />
                Discover Models
              </Button>
            )}
          </div>
          <Textarea
            placeholder={"One model ID per line, e.g.\ngpt-4o\ngpt-4o-mini"}
            value={modelsText}
            onChange={(e) => setModelsText(e.target.value)}
            rows={5}
            className="resize-y text-sm font-mono"
            disabled={isSaving}
          />
        </div>

        {/* Actions */}
        <div className="flex justify-end mt-2 gap-2">
          {isEditing && !showDeleteConfirm && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowDeleteConfirm(true)}
              disabled={isSaving || isDeleting}
            >
              Delete
            </Button>
          )}
          {showDeleteConfirm && (
            <>
              <span className="text-xs text-destructive self-center mr-auto">
                Are you sure?
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDelete}
                loading={isDeleting}
                disabled={isDeleting}
              >
                Confirm Delete
              </Button>
            </>
          )}
          {!showDeleteConfirm && (
            <Button
              onClick={handleSave}
              size="sm"
              loading={isSaving}
              disabled={!canSave || isSaving}
            >
              {isEditing ? "Save Changes" : "Create Provider"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default CustomProviderForm;
