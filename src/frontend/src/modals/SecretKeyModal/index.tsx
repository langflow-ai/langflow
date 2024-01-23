import * as Form from "@radix-ui/react-form";
import { useEffect, useRef, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { createApiKey } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import { ApiKeyType } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";
import BaseModal from "../baseModal";

export default function SecretKeyModal({
  title,
  cancelText,
  confirmationText,
  children,
  icon,
  data,
  onCloseModal,
}: ApiKeyType) {
  const Icon: any = nodeIconsLucide[icon];
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
      onCloseModal();
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
        title: "API Key copied!",
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

  return (
    <BaseModal size="small-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Header description={""}>
        <span className="pr-2">{title}</span>
        <Icon
          name="icon"
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        {renderKey === true && (
          <>
            <span className="text-xs">
              Please save this secret key somewhere safe and accessible. For
              security reasons,{" "}
              <strong>you won't be able to view it again</strong> through your
              account. If you lose this secret key, you'll need to generate a
              new one.
            </span>
            <div className="flex pt-3">
              <div className="w-full">
                <Input ref={inputRef} readOnly={true} value={apiKeyValue} />
              </div>

              <div>
                <Button
                  className="ml-3"
                  onClick={() => {
                    handleCopyClick();
                  }}
                >
                  {textCopied ? (
                    <IconComponent name="Copy" className="h-4 w-4" />
                  ) : (
                    <IconComponent name="Check" className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </>
        )}

        <Form.Root
          onSubmit={(event) => {
            setRenderKey(true);
            handleAddNewKey();
            event.preventDefault();
          }}
        >
          {renderKey === false && (
            <div className="grid gap-5">
              <Form.Field name="username">
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    justifyContent: "space-between",
                  }}
                >
                  <Form.Label className="data-[invalid]:label-invalid">
                    Name (optional){" "}
                  </Form.Label>
                </div>
                <Form.Control asChild>
                  <input
                    onChange={({ target: { value } }) => {
                      setApiKeyName(value);
                    }}
                    value={apiKeyName}
                    className="primary-input"
                    placeholder="My key name"
                  />
                </Form.Control>
              </Form.Field>
            </div>
          )}
          {renderKey === false && (
            <div className="float-right">
              <Button
                className="mr-3"
                variant="outline"
                onClick={() => {
                  setOpen(false);
                }}
              >
                {cancelText}
              </Button>

              <Form.Submit asChild>
                <Button className="mt-8">{confirmationText}</Button>
              </Form.Submit>
            </div>
          )}

          {renderKey === true && (
            <div className="float-right">
              <Button
                onClick={() => {
                  setOpen(false);
                  setRenderKey(false);
                }}
                className="mt-8"
              >
                Done
              </Button>
            </div>
          )}
        </Form.Root>
      </BaseModal.Content>
    </BaseModal>
  );
}
