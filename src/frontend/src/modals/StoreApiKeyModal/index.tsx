import * as Form from "@radix-ui/react-form";
import { useContext, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { AuthContext } from "../../contexts/authContext";
import { addApiKeyStore } from "../../controllers/API";
import useAlertStore from "../../stores/alertStore";
import { useStoreStore } from "../../stores/storeStore";
import { StoreApiKeyType } from "../../types/components";
import BaseModal from "../baseModal";

export default function StoreApiKeyModal({
  children,
  disabled = false,
}: StoreApiKeyType) {
  if (disabled) return <>{children}</>;
  const [open, setOpen] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { storeApiKey } = useContext(AuthContext);
  const [apiKeyValue, setApiKeyValue] = useState("");

  const validApiKey = useStoreStore((state) => state.validApiKey);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);
  const setHasApiKey = useStoreStore((state) => state.updateHasApiKey);
  const setValidApiKey = useStoreStore((state) => state.updateValidApiKey);
  const setLoadingApiKey = useStoreStore((state) => state.updateLoadingApiKey);

  const handleSaveKey = () => {
    if (apiKeyValue) {
      addApiKeyStore(apiKeyValue).then(
        () => {
          setSuccessData({
            title: "Success! Your API Key has been saved.",
          });
          storeApiKey(apiKeyValue);
          setOpen(false);
          setHasApiKey(true);
          setValidApiKey(true);
          setLoadingApiKey(false);
        },
        (error) => {
          setErrorData({
            title: "There was an error saving the API Key, please try again.",
            list: [error["response"]["data"]["detail"]],
          });
          setHasApiKey(false);
          setValidApiKey(false);
          setLoadingApiKey(false);
        }
      );
    }
  };

  return (
    <BaseModal size="small-h-full" open={open && !disabled} setOpen={setOpen}>
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
      <BaseModal.Header
        description={
          (hasApiKey && !validApiKey
            ? "Your API key is not valid. "
            : !hasApiKey
            ? "You don't have an API key. "
            : "") + "Insert your Langflow API key."
        }
      >
        <span className="pr-2">API Key</span>
        <IconComponent
          name="Key"
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <Form.Root
          onSubmit={(event) => {
            event.preventDefault();
          }}
        >
          <div className="grid gap-5">
            <Form.Field name="apikey">
              <div className="flex items-center justify-between gap-2">
                <Form.Control asChild>
                  <Input
                    //fake api key
                    value={apiKeyValue}
                    type="password"
                    onChange={({ target: { value } }) => {
                      setApiKeyValue(value);
                    }}
                    placeholder="Insert your API Key"
                  />
                </Form.Control>
              </div>
            </Form.Field>
          </div>
          <div className="flex items-end justify-between">
            <span className="pr-1 text-xs text-muted-foreground">
              Don’t have an API key? Sign up at{" "}
              <a
                className="text-high-indigo underline"
                href="https://langflow.store/"
                target="_blank"
              >
                langflow.store
              </a>
            </span>
            <div className="">
              <Button
                className="mr-3"
                variant="outline"
                onClick={() => {
                  setOpen(false);
                }}
              >
                Cancel
              </Button>

              <Form.Submit asChild>
                <Button
                  className="mt-8"
                  onClick={() => {
                    handleSaveKey();
                  }}
                >
                  Save
                </Button>
              </Form.Submit>
            </div>
          </div>
        </Form.Root>
      </BaseModal.Content>
    </BaseModal>
  );
}
