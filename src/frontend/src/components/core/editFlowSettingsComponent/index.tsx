import React, { ChangeEvent, useState } from "react";
import { InputProps } from "../../../types/components";
import { cn, isEndpointNameValid } from "../../../utils/utils";
import { Input } from "../../ui/input";
import { Label } from "../../ui/label";
import { Textarea } from "../../ui/textarea";

export const EditFlowSettings: React.FC<InputProps> = ({
  name,
  invalidNameList = [],
  description,
  endpointName,
  maxLength = 50,
  minLength = 1,
  setName,
  setDescription,
  setEndpointName,
}: InputProps): JSX.Element => {
  const [isMaxLength, setIsMaxLength] = useState(false);
  const [isMinLength, setIsMinLength] = useState(false);
  const [validEndpointName, setValidEndpointName] = useState(true);
  const [isInvalidName, setIsInvalidName] = useState(false);

  const handleNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { value } = event.target;
    if (value.length >= maxLength) {
      setIsMaxLength(true);
    } else {
      setIsMaxLength(false);
    }
    if (value.length < minLength) {
      setIsMinLength(true);
    } else {
      setIsMinLength(false);
    }
    let invalid = false;
    for (let i = 0; i < invalidNameList!.length; i++) {
      if (value === invalidNameList![i]) {
        invalid = true;
        break;
      }
      invalid = false;
    }
    setIsInvalidName(invalid);

    // Only update the name if it's valid (not empty and not invalid)
    if (value.length >= minLength && !invalid) {
      setName!(value);
    } else if (value.length === 0) {
      // For empty string, update state but keep isMinLength true
      setName!("");
      setIsMinLength(true);
    }
  };

  const handleDescriptionChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setDescription!(event.target.value);
  };

  const handleEndpointNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { value } = event.target;
    // Validate the endpoint name
    // use this regex r'^[a-zA-Z0-9_-]+$'
    const isValid = isEndpointNameValid(event.target.value, maxLength);
    setValidEndpointName(isValid);

    // Only update if valid and meets minimum length (if set)
    if (isValid && value.length >= minLength) {
      setEndpointName!(value);
    } else if (value.length === 0) {
      // Always allow empty endpoint name (it's optional)
      setEndpointName!("");
    }
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
          {isMinLength && (
            <span className="edit-flow-span">
              Minimum {minLength} character(s) required
            </span>
          )}
          {isInvalidName && (
            <span className="edit-flow-span">
              Name invalid or already exists
            </span>
          )}
        </div>
        {setName ? (
          <Input
            className="nopan nodelete nodrag noflow mt-2 font-normal"
            onChange={handleNameChange}
            type="text"
            name="name"
            value={name ?? ""}
            placeholder="Flow name"
            id="name"
            maxLength={maxLength}
            minLength={minLength}
            required={true}
            onDoubleClickCapture={(event) => {
              handleFocus(event);
            }}
            data-testid="input-flow-name"
          />
        ) : (
          <span className="font-normal text-muted-foreground word-break-break-word">
            {name}
          </span>
        )}
      </Label>
      <Label>
        <div className="edit-flow-arrangement mt-3">
          <span className="font-medium">
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
            className="mt-2 max-h-[250px] resize-none font-normal"
            rows={5}
            onDoubleClickCapture={(event) => {
              handleFocus(event);
            }}
          />
        ) : (
          <div
            className={cn(
              "max-h-[250px] overflow-auto pt-2 font-normal text-muted-foreground word-break-break-word",
              description === "" ? "font-light italic" : "",
            )}
          >
            {description === "" ? "No description" : description}
          </div>
        )}
      </Label>
      {setEndpointName && (
        <Label>
          <div className="edit-flow-arrangement mt-3">
            <span className="font-medium">Endpoint Name</span>
            {!validEndpointName && (
              <span className="edit-flow-span">
                Invalid endpoint name. Use only letters, numbers, hyphens, and
                underscores ({maxLength} characters max).
              </span>
            )}
          </div>
          <Input
            className="nopan nodelete nodrag noflow mt-2 font-normal"
            onChange={handleEndpointNameChange}
            type="text"
            name="endpoint_name"
            value={endpointName ?? ""}
            placeholder="An alternative name to run the endpoint"
            maxLength={maxLength}
            minLength={minLength}
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
