import { createContext } from "react";
import React, { useState } from "react";

// context to set JSX element on the DOM
export const PopUpContext = createContext({
  openPopUp: (popUpElement: JSX.Element) => {},
  closePopUp: () => {},
});

interface PopUpProviderProps {
  children: React.ReactNode;
}

const PopUpProvider = ({ children }: PopUpProviderProps) => {
  const [popUpElements, setPopUpElements] = useState<JSX.Element[]>([]);

  const openPopUp = (element: JSX.Element) => {
    setPopUpElements((prevPopUps) => [element, ...prevPopUps]);
  };

  const closePopUp = () => {
    setPopUpElements((prevPopUps) => prevPopUps.slice(1));
  };

  return (
    <PopUpContext.Provider value={{ openPopUp, closePopUp }}>
      {children}
      {popUpElements[0]}
    </PopUpContext.Provider>
  );
};

export default PopUpProvider;
