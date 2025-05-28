import { classNames } from "@/utils/utils";

export const getButtonClassName = (disabled: boolean) =>
  classNames(disabled ? "text-hard-zinc" : "text-placeholder-foreground");
