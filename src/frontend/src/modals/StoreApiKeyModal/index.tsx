import * as Form from "@radix-ui/react-form";
import { useContext, useEffect, useRef, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { CONTROL_NEW_API_KEY } from "../../constants/constants";
import { alertContext } from "../../contexts/alertContext";
import { AuthContext } from "../../contexts/authContext";
import { StoreContext } from "../../contexts/storeContext";
import { addApiKeyStore } from "../../controllers/API";
import {
  ApiKeyInputType,
  StoreApiKeyType,
  inputHandlerEventType,
} from "../../types/components";
import BaseModal from "../baseModal";

export default function StoreApiKeyModal({
  children,
  onCloseModal,
}: StoreApiKeyType) {
  const [open, setOpen] = useState(false);
  const [inputState, setInputState] =
    useState<ApiKeyInputType>(CONTROL_NEW_API_KEY);
  const { setSuccessData, setErrorData } = useContext(alertContext);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { storeApiKey } = useContext(AuthContext);
  const { hasApiKey } = useContext(StoreContext);
  const [apiKeyValue, setApiKeyValue] = useState(
    hasApiKey ? "This is not a real api key." : ""
  );

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  useEffect(() => {
    if (open) {
      // resetForm();
    } else {
      onCloseModal();
    }
  }, [open]);

  const handleSaveKey = () => {
    if (inputState && inputState["apikey"]) {
      addApiKeyStore(inputState["apikey"]).then(
        () => {
          setSuccessData({
            title: "Success! Your API Key has been saved.",
          });
          storeApiKey(inputState["apikey"]);
          setOpen(false);
        },
        (error) => {
          setErrorData({
            title: "There was an error saving the API Key, please try again.",
            list: [error["response"]["data"]["detail"]],
          });
        }
      );
    }
  };

  return (
    <BaseModal size="small-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Header description={"Insert your Langflow API key."}>
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
            <Form.Field name="username">
              <div className="flex items-center justify-between gap-2">
                <Form.Control asChild>
                  <Input
                    //fake api key
                    value={apiKeyValue}
                    type="password"
                    onChange={({ target: { value } }) => {
                      handleInput({ target: { name: "apikey", value } });
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
