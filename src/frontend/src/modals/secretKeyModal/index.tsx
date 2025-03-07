import * as Form from "@radix-ui/react-form";
import { Label } from "@radix-ui/react-form";
import { useEffect, useRef, useState } from "react";
import { Input } from "../../components/ui/input";
import { COPIED_NOTICE_ALERT } from "../../constants/alerts_constants";
import { createApiKey } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import { ApiKeyType } from "../../types/components";
import BaseModal from "../baseModal";
import { ContentRenderKey } from "./components/content-render";
import { FormKeyRender } from "./components/form-key-render";
import { HeaderRender } from "./components/header-render";

interface ModalProps {
  generatedKeyMessage?: React.ReactNode;
  description?: React.ReactNode;
}

export default function SecretKeyModal({
  children,
  data,
  onCloseModal,
  modalProps,
}: ApiKeyType & { modalProps?: ModalProps }) {
  const [open, setOpen] = useState(false);
  const [apiKeyName, setApiKeyName] = useState(data?.apikeyname ?? "");
  const [apiKeyValue, setApiKeyValue] = useState("");
  const [renderKey, setRenderKey] = useState(false);
  const [textCopied, setTextCopied] = useState(true);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const inputRef = useRef<HTMLInputElement | null>(null);

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

  function handleSubmitForm() {
    if (!renderKey) {
      setRenderKey(true);
      handleAddNewKey();
    } else {
      setOpen(false);
    }
  }

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
            <>{modalProps?.generatedKeyMessage}</>
          ) : (
            <>{modalProps?.description}</>
          )
        }
      >
        <HeaderRender
          title={modalProps?.title}
          showIcon={modalProps?.showIcon}
        />
      </BaseModal.Header>
      <BaseModal.Content>
        {renderKey ? (
          <ContentRenderKey
            inputLabel={String(modalProps?.inputLabel ?? "")}
            inputRef={inputRef}
            apiKeyValue={apiKeyValue}
            handleCopyClick={handleCopyClick}
            textCopied={textCopied}
            renderKey={renderKey}
          />
        ) : (
          <FormKeyRender
            modalProps={modalProps}
            apiKeyName={apiKeyName}
            inputRef={inputRef}
            setApiKeyName={setApiKeyName}
          />
        )}
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{ label: renderKey ? "Done" : (modalProps?.buttonText ?? "") }}
      />
    </BaseModal>
  );
}
