import * as Form from "@radix-ui/react-form";
import InputComponent from "../../../../../components/core/parameterRenderComponent/components/inputComponent";
import { Button } from "../../../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../../../../../components/ui/card";
import {
  CREATE_API_KEY,
  INSERT_API_KEY,
  INVALID_API_KEY,
  NO_API_KEY,
} from "../../../../../constants/constants";

type StoreApiKeyFormComponentProps = {
  apikey: string;
  handleInput: (event: any) => void;
  handleSaveKey: (apikey: string, handleInput: any) => void;
  loadingApiKey: boolean;
  validApiKey: boolean;
  hasApiKey: boolean;
};
const StoreApiKeyFormComponent = ({
  apikey,
  handleInput,
  handleSaveKey,
  loadingApiKey,
  validApiKey,
  hasApiKey,
}: StoreApiKeyFormComponentProps) => {
  return (
    <>
      <Form.Root
        onSubmit={(event) => {
          event.preventDefault();
          handleSaveKey(apikey, handleInput);
        }}
      >
        <Card x-chunk="dashboard-04-chunk-2" id="api">
          <CardHeader>
            <CardTitle>Store API Key</CardTitle>
            <CardDescription>
              {(hasApiKey && !validApiKey
                ? INVALID_API_KEY
                : !hasApiKey
                  ? NO_API_KEY
                  : "") + INSERT_API_KEY}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex w-full flex-col gap-3">
              <div className="flex w-full gap-4">
                <Form.Field name="apikey" className="w-full">
                  <InputComponent
                    id="apikey"
                    onChange={(value) => {
                      handleInput({ target: { name: "apikey", value } });
                    }}
                    value={apikey}
                    isForm
                    password={true}
                    placeholder="Insert your API Key"
                    className="w-full"
                  />
                  <Form.Message match="valueMissing" className="field-invalid">
                    Please enter your API Key
                  </Form.Message>
                </Form.Field>
              </div>
              <span className="pr-1 text-xs text-muted-foreground">
                {CREATE_API_KEY}{" "}
                <a
                  className="text-high-indigo underline"
                  href="https://langflow.store/"
                  target="_blank"
                  rel="noopener"
                >
                  langflow.store
                </a>
              </span>
            </div>
          </CardContent>
          <CardFooter className="border-t px-6 py-4">
            <Form.Submit asChild>
              <Button
                loading={loadingApiKey}
                type="submit"
                data-testid="api-key-save-button-store"
              >
                Save
              </Button>
            </Form.Submit>
          </CardFooter>
        </Card>
      </Form.Root>
    </>
  );
};
export default StoreApiKeyFormComponent;
