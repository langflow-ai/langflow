import React, { ChangeEvent, useState } from "react";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";
import { InputProps } from "../../types/components";
import { cn } from "../../utils/utils";

export const EditFlowSettings: React.FC<InputProps> = ({
  name,
  invalidNameList,
  description,
  endpointName,
  maxLength = 50,
  setName,
  setDescription,
  setEndpointName,
}: InputProps): JSX.Element => {
  const [isMaxLength, setIsMaxLength] = useState(false);
  const [isEndpointNameValid, setIsEndpointNameValid] = useState(true);

  const handleNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { value } = event.target;
    if (value.length >= maxLength) {
      setIsMaxLength(true);
    } else {
      setIsMaxLength(false);
    }
    setName!(value);
  };

  const handleDescriptionChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setDescription!(event.target.value);
  };

  const handleEndpointNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    // Validate the endpoint name
    // use this regex r'^[a-zA-Z0-9_-]+$'
    const isValid =
      (/^[a-zA-Z0-9_-]+$/.test(event.target.value) &&
        event.target.value.length <= maxLength) ||
      // empty is also valid
      event.target.value.length === 0;
    setIsEndpointNameValid(isValid);
    setEndpointName!(event.target.value);
  };

  //this function is necessary to select the text when double clicking, this was not working with the onFocus event
  const handleFocus = (event) => event.target.select();

  return (
    <>
      <Label>
        <div className="edit-flow-arrangement">
          <span className="font-medium">Name{setName ? "" : ":"}</span>{" "}
          {isMaxLength && (
            <span className="edit-flow-span">Character limit reached</span>
          )}
        </div>
        {setName ? (
          <Input
            className="nopan nodelete nodrag noundo nocopy mt-2 font-normal"
            onChange={handleNameChange}
            type="text"
            name="name"
            value={name ?? ""}
            placeholder="Flow name"
            id="name"
            maxLength={maxLength}
            onDoubleClickCapture={(event) => {
              handleFocus(event);
            }}
          />
        ) : (
          <span className="font-normal text-muted-foreground word-break-break-word">
            {name}
          </span>
        )}
      </Label>
      <Label>
        <div className="edit-flow-arrangement mt-3">
          <span className="font-medium ">
            Description{setDescription ? " (optional)" : ":"}
          </span>
        </div>
        {setDescription ? (
          <Textarea
            name="description"
            id="description"
            onChange={handleDescriptionChange}
            value={description!}
            placeholder="Flow description"
            className="mt-2 max-h-[100px] resize-none font-normal"
            rows={3}
            onDoubleClickCapture={(event) => {
              handleFocus(event);
            }}
          />
        ) : (
          <span
            className={cn(
              "font-normal text-muted-foreground word-break-break-word",
              description === "" ? "font-light italic" : "",
            )}
          >
            {description === "" ? "No description" : description}
          </span>
        )}
      </Label>
      {setEndpointName && (
        <Label>
          <div className="edit-flow-arrangement mt-3">
            <span className="font-medium">Endpoint Name</span>
            {!isEndpointNameValid && (
              <span className="edit-flow-span">
                Invalid endpoint name. Use only letters, numbers, hyphens, and
                underscores ({maxLength} characters max).
              </span>
            )}
          </div>
          <Input
            className="nopan nodelete nodrag noundo nocopy mt-2 font-normal"
            onChange={handleEndpointNameChange}
            type="text"
            name="endpoint_name"
            value={endpointName ?? ""}
            placeholder="An alternative name to run the endpoint"
            maxLength={maxLength}
            id="endpoint_name"
            onDoubleClickCapture={(event) => {
              handleFocus(event);
            }}
          />
        </Label>
      )}
    </>
  );
};

export default EditFlowSettings;
