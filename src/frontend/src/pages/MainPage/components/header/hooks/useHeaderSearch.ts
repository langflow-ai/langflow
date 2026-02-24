import { debounce } from "lodash";
import { useCallback, useEffect, useState } from "react";

export const useHeaderSearch = (setSearch: (search: string) => void) => {
  const [inputValue, setInputValue] = useState("");

  const debouncedSetSearch = useCallback(
    debounce((value: string) => {
      setSearch(value);
    }, 1000),
    [setSearch],
  );

  useEffect(() => {
    debouncedSetSearch(inputValue);
    return () => {
      debouncedSetSearch.cancel();
    };
  }, [inputValue, debouncedSetSearch]);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  return { inputValue, handleSearch };
};
