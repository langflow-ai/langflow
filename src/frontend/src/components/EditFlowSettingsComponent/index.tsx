import React, { ChangeEvent, useEffect, useRef, useState } from "react";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";
import { readFlowsFromDatabase } from "../../controllers/API";

type InputProps = {
  name: string | null;
  description: string | null;
  maxLength?: number;
  flows: Array<{ id: string; name: string; description: string }>;
  tabId: string;
  invalidName: boolean;
  setInvalidName: (invalidName: boolean) => void;
  setName: (name: string) => void;
  setDescription: (description: string) => void;
  updateFlow: (flow: { id: string; name: string }) => void;
};

export const EditFlowSettings: React.FC<InputProps> = ({
  name,
  invalidName,
  setInvalidName,
  description,
  maxLength = 50,
  flows,
  tabId,
  setName,
  setDescription,
  updateFlow,
}) => {
  const [isMaxLength, setIsMaxLength] = useState(false);
  const nameLists = useRef([]);
  useEffect(() => {
    readFlowsFromDatabase().then((flows) => {
      flows.forEach((flow) => {
        nameLists.current.push(flow.name);
      });
    });
  }, []);

  const handleNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { value } = event.target;
    if (value.length >= maxLength) {
      setIsMaxLength(true);
    } else {
      setIsMaxLength(false);
    }
    if (!nameLists.current.includes(value)) {
      setInvalidName(false);
    } else {
      setInvalidName(true);
    }
    setName(value);
  };

  const [desc, setDesc] = useState(
    flows.find((flow) => flow.id === tabId).description
  );

  const handleDescriptionChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    flows.find((flow) => flow.id === tabId).description = event.target.value;
    setDesc(flows.find((flow) => flow.id === tabId).description);
    setDescription(event.target.value);
  };

  return (
    <>
      <Label>
        <div className="edit-flow-arrangement">
          <span className="font-medium">Name</span>{" "}
          {isMaxLength && (
            <span className="edit-flow-span">Character limit reached</span>
          )}
          {invalidName && (
            <span className="edit-flow-span">Name already in use</span>
          )}
        </div>
        <Input
          className="nopan nodrag noundo nocopy mt-2 font-normal"
          onChange={handleNameChange}
          type="text"
          name="name"
          value={name ?? ""}
          placeholder="File name"
          id="name"
          maxLength={maxLength}
        />
      </Label>
      <Label>
        <div className="edit-flow-arrangement mt-3">
          <span className="font-medium ">Description (optional)</span>
        </div>

        <Textarea
          name="description"
          id="description"
          onChange={handleDescriptionChange}
          value={desc}
          placeholder="Flow description"
          className="mt-2 max-h-[100px] font-normal"
          rows={3}
        />
      </Label>
    </>
  );
};

export default EditFlowSettings;
