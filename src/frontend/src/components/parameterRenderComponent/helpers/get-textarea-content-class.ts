import { cn } from "@/utils/utils";

export const getTextAreaContentClasses = ({
  editNode,
  disabled,
  password,
  value,
  textAreaContentClasses,
}) => {
  return cn(
    textAreaContentClasses.base,
    editNode ? textAreaContentClasses.editNode : textAreaContentClasses.normal,
    disabled && !editNode && textAreaContentClasses.disabled,
    disabled && editNode && textAreaContentClasses.disabledEditNode,
    password !== undefined &&
      password &&
      value !== "" &&
      textAreaContentClasses.password,
  );
};
