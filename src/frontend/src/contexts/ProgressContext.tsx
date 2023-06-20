import { createContext, useContext, useState } from "react";
import _ from "lodash";
//types for progressContext
type progressContextType = {
  setProgress: (newState: number) => void;
  progress: number;
};
const initialValue = {
  setProgress: () => {},
  progress: 0,
};
export const progressContext = createContext<progressContextType>(initialValue);
export function useProgress() {
  return useContext(progressContext);
}

export function ProgressProvider({ children }) {
  const [progress, setProgress] = useState(0);

  return (
    <progressContext.Provider
      value={{
        setProgress,
        progress,
      }}
    >
      {children}
    </progressContext.Provider>
  );
}
