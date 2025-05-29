import { useCallback, useState } from "react";

export const useAlternate = (
  initialState: boolean = false,
): [boolean, () => void, (value: boolean) => void] => {
  const [switched, setSwitched] = useState(initialState);
  const set = useCallback((value) => setSwitched(value), []);

  const alternate = useCallback(
    () => setSwitched((prevState) => !prevState),
    [],
  );
  return [switched, alternate, set];
};
