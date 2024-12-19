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
    disabled && textAreaContentClasses.disabled,
    password !== undefined &&
      password &&
      value !== "" &&
      textAreaContentClasses.password,
  );
};
