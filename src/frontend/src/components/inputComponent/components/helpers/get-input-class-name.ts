import { cn } from "@/utils/utils";

export const getInputClassName = ({
  disabled,
  password,
  setSelectedOption,
  selectedOption,
  pwdVisible,
  value,
  editNode,
  setSelectedOptions,
  isSelected,
  areOptionsSelected,
  className,
}) => {
  const classes = {
    base: className || "",
    password:
      password &&
      (!setSelectedOption || selectedOption === "") &&
      !pwdVisible &&
      value !== ""
        ? "text-clip password"
        : "",
    editNode: editNode ? "input-edit-node" : "",
    paddingRight: (() => {
      if (password && (setSelectedOption || setSelectedOptions))
        return "pr-[70px]";
      if (
        (!password && (setSelectedOption || setSelectedOptions)) ||
        (password && !(setSelectedOption || setSelectedOptions))
      )
        return "pr-8";
      return "";
    })(),
    selected:
      isSelected || areOptionsSelected
        ? "font-jetbrains text-sm font-medium text-foreground"
        : "",
  };

  return cn(
    classes.base,
    classes.password,
    classes.editNode,
    classes.paddingRight,
    classes.selected,
  );
};
