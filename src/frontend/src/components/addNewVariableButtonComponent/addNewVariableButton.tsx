import { useState } from "react";
import { registerGlobalVariable } from "../../controllers/API";
import BaseModal from "../../modals/baseModal";
import useAlertStore from "../../stores/alertStore";
import { useGlobalVariablesStore } from "../../stores/globalVariables";
import { ResponseErrorDetailAPI } from "../../types/api";
import ForwardedIconComponent from "../genericIconComponent";
import InputComponent from "../inputComponent";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";

//TODO IMPLEMENT FORM LOGIC

export default function AddNewVariableButton({ children }): JSX.Element {
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [provider, setProvider] = useState("");
  const [open, setOpen] = useState(false);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const addGlobalVariable = useGlobalVariablesStore(
    (state) => state.addGlobalVariable
  );
  function handleSaveVariable() {
    let data: { name: string; value: string; provider?: string } = {
      name: key,
      value,
    };
    if (provider) data = { ...data, provider };
    registerGlobalVariable(data)
      .then((res) => {
        const { name, id, provider } = res.data;
        addGlobalVariable(name, id, provider);
        setKey("");
        setValue("");
        setProvider("");
        setOpen(false);
      })
      .catch((error) => {
        let responseError = error as ResponseErrorDetailAPI;
        setErrorData({
          title: "Error creating variable",
          list: [responseError.response.data.detail ?? "Unknown error"],
        });
      });
  }
  return (
    <BaseModal open={open} setOpen={setOpen} size="x-small">
      <BaseModal.Header
        description={
          "This variable will be encrypted and will be available for you to use in any of your projects."
        }
      >
        <span className="pr-2"> Create Variable </span>
        <ForwardedIconComponent
          name="Globe"
          className="h-6 w-6 pl-1 text-primary "
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Content>
        <div className="flex h-full w-full flex-col gap-4 align-middle">
          <Label>Variable name </Label>
          <Input
            value={key}
            onChange={(e) => {
              setKey(e.target.value);
            }}
            placeholder="Insert a name for the variable..."
          ></Input>
          <Label>Provider (optional) </Label>
          <InputComponent
            setSelectedOption={(e) => {
              setProvider(e);
            }}
            selectedOption={provider}
            password={false}
            options={["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]}
            placeholder="Choose a provider between the environment variables..."
          ></InputComponent>
          <Label>Variable Value </Label>
          <Textarea
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
            }}
            placeholder="Insert a value for the variable..."
            className="w-full resize-none custom-scroll"
          />
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <Button onClick={handleSaveVariable}>Save variable</Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
