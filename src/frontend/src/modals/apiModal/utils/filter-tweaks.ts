import { INPUT_TYPES } from "@/constants/constants";

export function formatPayloadTweaks(tweaksObject: any): boolean {
  if (!tweaksObject || typeof tweaksObject !== "object") {
    return true;
  }

  const InputTypes = [...Array.from(INPUT_TYPES), "TextInput"];

  const hasInputValueInTweaks = Object.keys(tweaksObject).some((key) => {
    const isInputNode = Array.from(InputTypes).some((inputType) =>
      key.startsWith(inputType),
    );

    return (
      isInputNode &&
      tweaksObject[key] &&
      typeof tweaksObject[key] === "object" &&
      "input_value" in tweaksObject[key]
    );
  });

  return !hasInputValueInTweaks;
}
