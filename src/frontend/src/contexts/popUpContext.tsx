import { createContext } from "react";
import React, { useState } from "react";

//context to set JSX element on the DOM
export const PopUpContext = createContext({
  openPopUp: (popUpElement: JSX.Element) => {},
	closePopUp: () => {},
});

interface PopUpProviderProps {
	children: React.ReactNode;
}

const PopUpProvider = ({ children }: PopUpProviderProps) => {
	const [popUpElement, setPopUpElement] = useState<JSX.Element | null>(null);

	const openPopUp = (element: JSX.Element) => {
		setPopUpElement(element);
	};

	const closePopUp = () => {
		setPopUpElement(null);
	};

	return (
		<PopUpContext.Provider value={{ openPopUp, closePopUp }}>
			{children}
			{popUpElement}
		</PopUpContext.Provider>
	);
};

export default PopUpProvider;
