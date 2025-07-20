import * as Form from "@radix-ui/react-form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const FormKeyRender = ({
  modalProps,
  apiKeyName,
  inputRef,
  setApiKeyName,
}: {
  modalProps: any;
  apiKeyName: string;
  inputRef: React.RefObject<HTMLInputElement>;
  setApiKeyName: (value: string) => void;
}) => {
  return (
    <Form.Field name="apikey">
      {modalProps?.inputLabel && (
        <Form.Label asChild className="mb-2">
          <Label className="relative bottom-1">
            {modalProps?.inputLabel as React.ReactNode}
          </Label>
        </Form.Label>
      )}

      <div className="flex items-center justify-between gap-2">
        <Form.Control asChild>
          <Input
            id="primary-input"
            value={apiKeyName}
            ref={inputRef}
            onChange={({ target: { value } }) => {
              setApiKeyName(value);
            }}
            placeholder={modalProps?.inputPlaceholder}
          />
        </Form.Control>
      </div>
    </Form.Field>
  );
};
