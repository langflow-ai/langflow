import React, { ChangeEvent, useState } from "react";
import { InputProps } from "../../../types/components";
import { cn } from "../../../utils/utils";
import { Input } from "../../ui/input";
import { Label } from "../../ui/label";
import { Textarea } from "../../ui/textarea";

export const EditFlowSettings: React.FC<InputProps> = ({
  name,
  invalidNameList = [],
  description,
  maxLength = 50,
  descriptionMaxLength = 250,
  minLength = 1,
  setName,
  setDescription,
}: InputProps): JSX.Element => {
  const [isMaxLength, setIsMaxLength] = useState(false);
  const [isMaxDescriptionLength, setIsMaxDescriptionLength] = useState(false);
  const [isMinLength, setIsMinLength] = useState(false);
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

    setName!(value);

    if (value.length === 0) {
      // For empty string, update state but keep isMinLength true
      setIsMinLength(true);
    }
  };

  const handleDescriptionChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    const { value } = event.target;
    if (value.length >= descriptionMaxLength) {
      setIsMaxDescriptionLength(true);
    } else {
      setIsMaxDescriptionLength(false);
    }
    setDescription!(value);
  };

  //this function is necessary to select the text when double clicking, this was not working with the onFocus event
  const handleFocus = (event) => event.target.select();

  return (
    <>
      <Label>
        <div className="edit-flow-arrangement">
          <span className="text-mmd font-medium">Name{setName ? "" : ":"}</span>{" "}
          {isMaxLength && (
            <span className="edit-flow-span">Character limit reached</span>
          )}
          {isMinLength && (
            <span className="edit-flow-span">
              Minimum {minLength} character(s) required
            </span>
          )}
          {isInvalidName && (
            <span className="edit-flow-span">Flow name already exists</span>
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
          <span className="text-mmd font-medium">
            Description{setDescription ? "" : ":"}
          </span>
          {isMaxDescriptionLength && (
            <span className="edit-flow-span">Character limit reached</span>
          )}
        </div>
        {setDescription ? (
          <Textarea
            name="description"
            id="description"
            onChange={handleDescriptionChange}
            value={description!}
            placeholder="Flow description"
            data-testid="input-flow-description"
            className="mt-2 max-h-[250px] resize-none font-normal"
            rows={5}
            maxLength={descriptionMaxLength}
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
    </>
  );
};

export default EditFlowSettings;
