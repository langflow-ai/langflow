import { createContext, useState } from "react";

type darkContextType = {
	dark: {};
	setDark: (newState: {}) => void;
};

const initialValue = {
	dark: {},
	setDark: () => {},
};

export const darkContext = createContext<darkContextType>(initialValue);

export function DarkProvider({ children }) {
	const [dark, setDark] = useState(false);
	return (
		<darkContext.Provider
			value={{
				dark,
				setDark,
			}}
		>
			{children}
		</darkContext.Provider>
	);
}