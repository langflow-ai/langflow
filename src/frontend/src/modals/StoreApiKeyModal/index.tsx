import * as Form from "@radix-ui/react-form";
import { useContext, useEffect, useRef, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { CONTROL_NEW_API_KEY } from "../../constants/constants";
import { alertContext } from "../../contexts/alertContext";
import { AuthContext } from "../../contexts/authContext";
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
  const [apiKeyValue, setApiKeyValue] = useState("");
  const [inputState, setInputState] =
    useState<ApiKeyInputType>(CONTROL_NEW_API_KEY);
  const { setSuccessData, setErrorData } = useContext(alertContext);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { storeApiKey } = useContext(AuthContext);

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  useEffect(() => {
    if (open) {
      resetForm();
    } else {
      onCloseModal();
    }
  }, [open]);

  function resetForm() {
    setApiKeyValue("");
  }

  const handleSaveKey = () => {
    if (inputState && inputState["apikey"]) {
      addApiKeyStore(inputState["apikey"]).then(
        () => {
          setSuccessData({
            title: "Success! Your API Key has been saved.",
          });
          storeApiKey("9bxW74lS1qee3UWKMx3Vydxu5wxPqC8W");
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
      <BaseModal.Header
        description={
          "Insert your Langflow API key. If you don't have it, please sign up."
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
            <Form.Field name="username">
              <div className="flex items-center justify-between gap-2">
                <a href="https://langflow.store/" target="_blank">
                  <Button type="button" className="w-24" variant="secondary">
                    Sign up
                  </Button>
                </a>
                <Form.Control asChild>
                  <Input
                    onChange={({ target: { value } }) => {
                      handleInput({ target: { name: "apikey", value } });
                    }}
                    placeholder="Insert your API Key"
                  />
                </Form.Control>
              </div>
            </Form.Field>
          </div>
          <div className="float-right">
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
        </Form.Root>
      </BaseModal.Content>
    </BaseModal>
  );
}
