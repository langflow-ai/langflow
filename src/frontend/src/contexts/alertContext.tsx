import React, { createContext, useState } from "react";

interface ErrorData {
  title: string;
  list: string[];
}

interface AlertContextType {
  errorData: ErrorData | null;
  setErrorData: (data: ErrorData | null) => void;
}

export const alertContext = createContext<AlertContextType>({
  errorData: null,
  setErrorData: () => {},
});

export function AlertProvider({ children }: { children: React.ReactNode }) {
  const [errorData, setErrorData] = useState<ErrorData | null>(null);

  return (
    <alertContext.Provider
      value={{
        errorData,
        setErrorData,
      }}
    >
      {children}
    </alertContext.Provider>
  );
}
