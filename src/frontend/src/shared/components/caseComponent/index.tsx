import { memo } from "react";

type BooleanLike = boolean | string | number | null | undefined;

type Props = {
  condition: (() => BooleanLike) | BooleanLike;
  children: React.ReactNode | any;
};

export const Case = memo(({ condition, children }: Props) => {
  const conditionResult =
    typeof condition === "function" ? condition() : condition;

  return conditionResult ? children : null;
});
