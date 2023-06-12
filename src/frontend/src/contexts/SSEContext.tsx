import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";

const initialValue = {
  updateSSEData: ({}) => {},
  sseData: {},
};

const SSEContext = createContext(initialValue);

export function useSSE() {
  return useContext(SSEContext);
}

export function SSEProvider({ children }) {
  const [sseData, setSSEData] = useState({});

  const updateSSEData = useCallback((newData: any) => {
    setSSEData((prevData) => ({
      ...prevData,
      ...newData,
    }));
  }, []);

  return (
    <SSEContext.Provider value={{ sseData, updateSSEData }}>
      {children}
    </SSEContext.Provider>
  );
}
