import { createContext, ReactNode, useState } from "react";
import { Node } from "reactflow";
import { TemplateContextType } from "../types/templatesContext";
//context to share types adn functions from nodes to flow

const initialValue: TemplateContextType = {
	templates: {},
	setTemplates: () => {},
};

export const TemplatesContext =
	createContext<TemplateContextType>(initialValue);

export function TypesProvider({ children }: { children: ReactNode }) {
	const [templates, setTemplates] = useState({});
	return (
		<TemplatesContext.Provider value={{ templates, setTemplates }}>
			{children}
		</TemplatesContext.Provider>
	);
}
