import type { InputProps, StrRenderComponentType } from "../../types";
import CopyFieldAreaComponent from "../copyFieldAreaComponent";
import DropdownComponent from "../dropdownComponent";
import InputGlobalComponent from "../inputGlobalComponent";
import TextAreaComponent from "../textAreaComponent";
import WebhookFieldComponent from "../webhookFieldComponent";
import GenesisPromptTextArea from "@/customization/components/genesis-prompt-text-area";
import GenesisPromptDropdown from "@/customization/components/genesis-prompt-dropdown";
import { useUpdateVersion } from "@/controllers/API/queries/prompt-library/use-update-version";
import { useSubmitForReview } from "@/controllers/API/queries/prompt-library/use-submit-for-review";
import useAlertStore from "@/stores/alertStore";

export function StrRenderComponent({
  templateData,
  name,
  display_name,
  placeholder,
  nodeId,
  nodeClass,
  handleNodeClass,
  ...baseInputProps
}: InputProps<string, StrRenderComponentType>) {
  const { handleOnNewValue, id, isToolMode, nodeInformationMetadata } =
    baseInputProps;

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Genesis Prompt API hooks (only used when prompt_id is present)
  const { mutate: updateVersion, isPending: isUpdating } = useUpdateVersion();
  const { mutate: submitForReview, isPending: isSubmitting } = useSubmitForReview();

  const noOptions = !templateData.options;
  const isMultiline = templateData.multiline;
  const copyField = templateData.copy_field;
  const hasOptions = !!templateData.options;
  const isWebhook = nodeInformationMetadata?.nodeType === "webhook";

  // Check if this is a Genesis Prompt field
  const promptId = (templateData as any).prompt_id;
  const promptVersion = (templateData as any).prompt_version;
  const versionStatus = (templateData as any).version_status;
  const isGenesisPrompt = !!promptId;

  // Handler for saving draft version (Genesis Prompt only)
  const handleSaveVersion = (newContent: string, onSuccess?: () => void) => {
    if (!promptId || !promptVersion) {
      return;
    }

    // Only allow saving DRAFT versions
    if (versionStatus && versionStatus !== "DRAFT") {
      setErrorData({
        title: "Cannot Save",
        list: ["Only draft versions can be edited"],
      });
      return;
    }

    // Get the current message type from nodeClass template
    const messageType = nodeClass?.template?.message_type?.value || "system";

    updateVersion(
      {
        promptId,
        version: promptVersion,
        message_chain: [
          {
            role: messageType,
            content: newContent,
            order: 0,
          },
        ],
        variables: [],
        change_description: "Updated via Genesis Studio",
      },
      {
        onSuccess: () => {
          setSuccessData({ title: "Version saved successfully" });
          handleOnNewValue({ value: newContent });
          // Call the success callback (e.g., to close the modal)
          onSuccess?.();
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to save version",
            list: [error?.response?.data?.detail || error.message || "Unknown error"],
          });
        },
      }
    );
  };

  // Handler for submitting for review (Genesis Prompt only)
  const handleSubmitForReview = (comment?: string) => {
    if (!promptId || !promptVersion) {
      setErrorData({
        title: "Cannot Submit",
        list: ["No prompt version selected"],
      });
      return;
    }

    submitForReview(
      {
        promptId,
        version: promptVersion,
        comment,
      },
      {
        onSuccess: () => {
          setSuccessData({ title: "Submitted for review successfully" });
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to submit for review",
            list: [error?.response?.data?.detail || error.message || "Unknown error"],
          });
        },
      }
    );
  };

  if (noOptions) {
    if (isMultiline) {
      if (isWebhook) {
        return <WebhookFieldComponent {...baseInputProps} />;
      }

      if (copyField) {
        return <CopyFieldAreaComponent {...baseInputProps} />;
      }

      // Use Genesis-specific component if prompt_id is set
      if (isGenesisPrompt) {
        return (
          <GenesisPromptTextArea
            {...baseInputProps}
            handleOnNewValue={handleOnNewValue}
            id={`textarea_${id}`}
            isToolMode={isToolMode}
            promptId={promptId}
            promptVersion={promptVersion}
            versionStatus={versionStatus}
            onSaveVersion={handleSaveVersion}
            isSavingVersion={isUpdating}
            onSubmitForReview={handleSubmitForReview}
            isSubmittingForReview={isSubmitting}
            isLoading={(templateData as any).is_loading}
          />
        );
      }

      // Standard TextAreaComponent for non-Genesis fields
      return (
        <TextAreaComponent
          {...baseInputProps}
          updateVisibility={() => {
            if (templateData.password !== undefined) {
              handleOnNewValue(
                { password: !templateData.password },
                { skipSnapshot: true },
              );
            }
          }}
          id={`textarea_${id}`}
          isToolMode={isToolMode}
        />
      );
    }

    return (
      <InputGlobalComponent
        {...baseInputProps}
        password={templateData.password}
        load_from_db={templateData.load_from_db}
        placeholder={placeholder}
        display_name={display_name}
        id={`input-${name}`}
        isToolMode={isToolMode}
      />
    );
  }

  if (hasOptions) {
    // Use Genesis-specific dropdown for saved_prompt field (adds "Create new Prompt" button)
    const isGenesisPromptDropdown = name === "saved_prompt" && nodeClass?.display_name === "Genesis Prompt Template";
    
    if (isGenesisPromptDropdown) {
      return (
        <GenesisPromptDropdown
          id={id}
          value={baseInputProps.value}
          editNode={baseInputProps.editNode}
          handleOnNewValue={handleOnNewValue}
          disabled={baseInputProps.disabled}
          nodeId={nodeId}
          nodeClass={nodeClass}
          handleNodeClass={handleNodeClass}
          name={templateData?.name!}
          options={templateData.options ?? []}
          optionsMetaData={templateData.options_metadata}
          placeholder={placeholder}
          combobox={templateData.combobox}
          dialogInputs={templateData.dialog_inputs}
          externalOptions={templateData.external_options}
          toggle={templateData.toggle}
          hasRefreshButton={templateData.refresh_button}
        />
      );
    }

    return (
      <DropdownComponent
        {...baseInputProps}
        dialogInputs={templateData.dialog_inputs}
        externalOptions={templateData.external_options}
        options={templateData.options ?? []}
        nodeId={nodeId}
        nodeClass={nodeClass}
        placeholder={placeholder}
        handleNodeClass={handleNodeClass}
        optionsMetaData={templateData.options_metadata}
        combobox={templateData.combobox}
        name={templateData?.name!}
        toggle={templateData.toggle}
        toggleValue={templateData.toggle_value}
        toggleDisable={templateData.toggle_disable}
        hasRefreshButton={templateData.refresh_button}
      />
    );
  }
}
