import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { useGenerateToken } from "@/customization/hooks/use-custom-generate-token";
import { useEffect, useRef, useState } from "react";
import { COPIED_NOTICE_ALERT } from "../../constants/alerts_constants";
import { createApiKey } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import type { ApiKeyType } from "../../types/components";
import BaseModal from "../baseModal";
import { ContentRenderKey } from "./components/content-render";
import { FormKeyRender } from "./components/form-key-render";
import { HeaderRender } from "./components/header-render";

// Add this interface for the modal props
interface ModalConfigProps {
  title?: string;
  description?: React.ReactNode;
  inputLabel?: React.ReactNode;
  inputPlaceholder?: string;
  buttonText?: string;
  generatedKeyMessage?: React.ReactNode;
  showIcon?: boolean;
}

interface SecretKeyModalProps {
  userId?: string;
  size?: string;
  modalProps?: ModalConfigProps;
}

export default function SecretKeyModal({
  children,
  data,
  onCloseModal,
  modalProps,
}: ApiKeyType & { modalProps: SecretKeyModalProps }) {
  const [open, setOpen] = useState(false);
  const [apiKeyName, setApiKeyName] = useState(data?.apikeyname ?? "");
  const [apiKeyValue, setApiKeyValue] = useState("");
  const [renderKey, setRenderKey] = useState(false);
  const [textCopied, setTextCopied] = useState(true);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const generateToken = useGenerateToken();
  const modalConfigProps = modalProps?.modalProps ?? modalProps;

  useEffect(() => {
    if (open) {
      setRenderKey(false);
      resetForm();
    } else {
      onCloseModal?.();
    }
  }, [open]);

  function resetForm() {
    setApiKeyName("");
    setApiKeyValue("");
  }

  const handleCopyClick = async () => {
    if (apiKeyValue) {
      await navigator.clipboard.writeText(apiKeyValue);
      inputRef?.current?.focus();
      inputRef?.current?.select();
      setSuccessData({
        title: COPIED_NOTICE_ALERT,
      });
      setTextCopied(false);

      setTimeout(() => {
        setTextCopied(true);
      }, 3000);
    }
  };

  function handleAddNewKey() {
    createApiKey(apiKeyName)
      .then((res) => {
        setApiKeyValue(res["api_key"]);
      })
      .catch((err) => {});
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
          <FormKeyRender
            modalProps={modalConfigProps}
            apiKeyName={apiKeyName}
            inputRef={inputRef}
            setApiKeyName={setApiKeyName}
          />
        )}
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: renderKey ? "Done" : (modalConfigProps?.buttonText ?? ""),
        }}
      />
    </BaseModal>
  );
}
