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
  isBuilding: false,
  setIsBuilding: (isBuilding: boolean) => {},
  setStatus : (status: number) => {},
  status: 0,
};

const SSEContext = createContext(initialValue);

export function useSSE() {
  return useContext(SSEContext);
}

export function SSEProvider({ children }) {
  const [sseData, setSSEData] = useState({});
  const [isBuilding, setIsBuilding] = useState(false);
  const [status, setStatus] = useState(0);

  const updateSSEData = useCallback((newData: any) => {
    setSSEData((prevData) => ({
      ...prevData,
      ...newData,
    }));
  }, []);

  return (
    <SSEContext.Provider
      value={{ setStatus,status,sseData, updateSSEData, isBuilding, setIsBuilding }}
    >
      {children}
    </SSEContext.Provider>
  );
}
