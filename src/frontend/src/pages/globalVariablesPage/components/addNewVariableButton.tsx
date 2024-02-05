import { useState } from "react";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Textarea } from "../../../components/ui/textarea";
import { registerGlobalVariable } from "../../../controllers/API";
import BaseModal from "../../../modals/baseModal";
import { useGlobalVariablesStore } from "../../../stores/globalVariables";

//TODO IMPLEMENT FORM LOGIC

export default function AddNewVariableButton(): JSX.Element {
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [open, setOpen] = useState(false);
  const addGlobalVariable = useGlobalVariablesStore(
    (state) => state.addGlobalVariable
  );
  function handleSaveVariable() {
    registerGlobalVariable(key, value).then((_) => {
      addGlobalVariable(key, value);
      setKey("");
      setValue("");
      setOpen(false);
    });
  }
  return (
    <BaseModal open={open} setOpen={setOpen} size="small">
      <BaseModal.Header
        description={"write a text variable to use anywhere on your flow"}
      >
        <span>Create a new Variable</span>
      </BaseModal.Header>
      <BaseModal.Trigger>
        <Button>Create a new variable</Button>
      </BaseModal.Trigger>
      <BaseModal.Content>
        <div className="flex h-full w-full flex-col justify-around align-middle">
          <div className="h-1/2">
            <Label>Variable name </Label>
            <Input
              value={key}
              onChange={(e) => {
                setKey(e.target.value);
              }}
              placeholder="example name"
            ></Input>
          </div>
          <div className="h-1/2">
            <Label>Variable Value </Label>
            <Textarea
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
              }}
              className="h-4/6 w-full resize-none custom-scroll"
            />
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <Button onClick={handleSaveVariable}>Save variable</Button>
      </BaseModal.Footer>
    </BaseModal>
  );
}
