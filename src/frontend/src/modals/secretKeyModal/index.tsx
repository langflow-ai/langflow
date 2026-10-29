import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ApiKeyPermissionsEditor, {
  isApiKeyPermissionPolicyValid,
} from "@/components/core/apiKeyPermissionsEditor";
import { extractApiErrorMessage } from "@/controllers/API/helpers/extract-api-error-message";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { useGenerateToken } from "@/customization/hooks/use-custom-generate-token";
import type {
  ApiKeyPermissionOptions,
  ApiKeyPermissionPolicy,
} from "@/types/api-key-permissions";
import { createApiKey } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import type { ApiKeyType } from "../../types/components";
import BaseModal from "../baseModal";
import { ContentRenderKey } from "./components/content-render";
import { FormKeyRender } from "./components/form-key-render";
import { HeaderRender } from "./components/header-render";

export interface ModalConfigProps {
  title?: string;
  description?: React.ReactNode;
  inputLabel?: React.ReactNode;
  inputPlaceholder?: string;
  buttonText?: string;
  generatedKeyMessage?: React.ReactNode;
  showIcon?: boolean;
}

interface SecretKeyModalConfiguration extends ModalConfigProps {
  size?: NonNullable<ApiKeyType["modalProps"]>["size"];
  modalProps?: ModalConfigProps;
}

export default function SecretKeyModal({
  children,
  data,
  onCloseModal,
  modalProps,
  permissionOptions,
  permissionsLoading = false,
  permissionsError = false,
}: Omit<ApiKeyType, "modalProps"> & {
  modalProps?: SecretKeyModalConfiguration;
  permissionOptions?: ApiKeyPermissionOptions;
  permissionsLoading?: boolean;
  permissionsError?: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [apiKeyName, setApiKeyName] = useState(data?.apikeyname ?? "");
  const [apiKeyValue, setApiKeyValue] = useState("");
  const [expiresAt, setExpiresAt] = useState<string>("");
  const [renderKey, setRenderKey] = useState(false);
  const [textCopied, setTextCopied] = useState(true);
  // Key-creation failure, surfaced inline and associated with the name field
  // (WCAG 3.3.1) — it was previously swallowed entirely.
  const [serverError, setServerError] = useState<string | null>(null);
  const [permissions, setPermissions] = useState<ApiKeyPermissionPolicy | null>(
    null,
  );
  const [isCreating, setIsCreating] = useState(false);
  const [scopeEditorEnabled, setScopeEditorEnabled] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const generateToken = useGenerateToken();
  const modalConfigProps = modalProps?.modalProps ?? modalProps;

  useEffect(() => {
    if (open) {
      setRenderKey(false);
      setScopeEditorEnabled(Boolean(permissionOptions?.supported));
      resetForm();
    } else {
      onCloseModal?.();
    }
  }, [open]);

  useEffect(() => {
    if (open && permissionOptions?.supported) setScopeEditorEnabled(true);
  }, [open, permissionOptions?.supported]);

  function resetForm() {
    setApiKeyName("");
    setApiKeyValue("");
    setExpiresAt("");
    setServerError(null);
    setPermissions(null);
  }

  const handleCopyClick = async () => {
    if (apiKeyValue) {
      await navigator.clipboard.writeText(apiKeyValue);
      inputRef?.current?.focus();
      inputRef?.current?.select();
      setSuccessData({
        title: t("alerts.apiKeyCopied"),
      });
      setTextCopied(false);

      setTimeout(() => {
        setTextCopied(true);
      }, 3000);
    }
  };

  function handleAddNewKey() {
    // Append local end-of-day (no "Z" suffix) so the Date constructor treats it
    // as local time, giving UTC+ users a key that expires at midnight their time.
    const isoExpiry = expiresAt
      ? new Date(expiresAt + "T23:59:59").toISOString()
      : null;
    setIsCreating(true);
    const request = permissionOptions?.supported
      ? createApiKey(apiKeyName, isoExpiry, permissions)
      : createApiKey(apiKeyName, isoExpiry);
    request
      .then((res) => {
        setApiKeyValue(res["api_key"]);
      })
      .catch((err) => {
        // Return to the form view instead of showing an empty "generated key"
        // screen, and tell the user what went wrong. Raw 5xx detail ("Internal
        // Server Error") is no help — prefer the translated message there.
        setRenderKey(false);
        const status = err?.response?.status;
        setServerError(
          err?.code === "API_KEY_PERMISSION_MISMATCH"
            ? t("apiKey.permissions.policyNotApplied")
            : typeof status === "number" && status >= 500
              ? t("errors.errorGeneratingApiKey")
              : extractApiErrorMessage(err, t("errors.errorGeneratingApiKey")),
        );
      })
      .finally(() => setIsCreating(false));
  }

  async function handleSubmitForm() {
    if (apiKeyValue) setOpen(false);
    if (ENABLE_DATASTAX_LANGFLOW) {
      handleDataStaxKey();
    } else {
      handleOSSKey();
    }
  }

  const handleDataStaxKey = async () => {
    try {
      const { token } = await generateToken();
      setApiKeyValue(token);
      setRenderKey(true);
    } catch (error) {
      console.error("Error generating token:", error);
    }
  };

  const handleOSSKey = () => {
    if (!renderKey) {
      if (
        permissionsLoading ||
        permissionsError ||
        (scopeEditorEnabled && !permissionOptions?.supported) ||
        isCreating ||
        (permissionOptions?.supported &&
          !isApiKeyPermissionPolicyValid(permissions, permissionOptions))
      )
        return;
      setRenderKey(true);
      handleAddNewKey();
    } else {
      setOpen(false);
    }
  };

  return (
    <BaseModal
      onSubmit={handleSubmitForm}
      size={modalProps?.size ?? "small-h-full"}
      open={open}
      setOpen={setOpen}
    >
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
      <BaseModal.Header
        clampDescription={3}
        description={
          renderKey ? (
            <>{modalConfigProps?.generatedKeyMessage}</>
          ) : (
            <>{modalConfigProps?.description}</>
          )
        }
      >
        <HeaderRender
          title={modalConfigProps?.title}
          showIcon={modalConfigProps?.showIcon}
        />
      </BaseModal.Header>
      <BaseModal.Content>
        {renderKey ? (
          <ContentRenderKey
            inputLabel={String(modalConfigProps?.inputLabel ?? "")}
            inputRef={inputRef}
            apiKeyValue={apiKeyValue}
            handleCopyClick={handleCopyClick}
            textCopied={textCopied}
            renderKey={renderKey}
          />
        ) : ENABLE_DATASTAX_LANGFLOW ? (
          <></>
        ) : (
          <>
            <FormKeyRender
              modalProps={modalConfigProps}
              apiKeyName={apiKeyName}
              inputRef={inputRef}
              setApiKeyName={(value) => {
                setApiKeyName(value);
                setServerError(null);
              }}
              expiresAt={expiresAt}
              setExpiresAt={(value) => {
                setExpiresAt(value);
                setServerError(null);
              }}
              serverError={serverError}
            />
            {permissionsError && (
              <p role="alert" className="mt-4 text-sm text-destructive">
                {t("apiKey.permissions.optionsError")}
              </p>
            )}
            {scopeEditorEnabled &&
              !permissionOptions?.supported &&
              !permissionsError && (
                <p role="alert" className="mt-4 text-sm text-destructive">
                  {t("apiKey.permissions.unavailable")}
                </p>
              )}
            {permissionOptions?.supported && (
              <div className="mt-4">
                <ApiKeyPermissionsEditor
                  options={permissionOptions}
                  value={permissions}
                  onChange={(policy) => {
                    setPermissions(policy);
                    setServerError(null);
                  }}
                />
              </div>
            )}
          </>
        )}
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: renderKey
            ? t("modal.secretKey.doneButton")
            : (modalConfigProps?.buttonText ?? ""),
          dataTestId: "secret_key_modal_submit_button",
          loading: isCreating,
          disabled:
            !renderKey &&
            (permissionsLoading ||
              permissionsError ||
              (scopeEditorEnabled && !permissionOptions?.supported) ||
              isCreating ||
              Boolean(
                permissionOptions?.supported &&
                  !isApiKeyPermissionPolicyValid(
                    permissions,
                    permissionOptions,
                  ),
              )),
        }}
      />
    </BaseModal>
  );
}
