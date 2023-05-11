import { createContext, useEffect, useState } from "react";

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
	useEffect(() => {
		if (dark) {
			document.getElementById("body").classList.add("dark");
		} else {
			document.getElementById("body").classList.remove("dark");
		}
	}, [dark]);
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
