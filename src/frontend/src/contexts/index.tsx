import { ReactNode } from "react";
import { AlertProvider } from "./alertContext";
import { DarkProvider } from "./darkContext";
import { LocationProvider } from "./locationContext";
import PopUpProvider from "./popUpContext";
import { TabsProvider } from "./tabsContext";
import { TypesProvider } from "./typesContext";

export default function ContextWrapper({ children }: { children: ReactNode }) {
	//element to wrap all context
	return (
		<>
			<DarkProvider>
				<LocationProvider>
					<AlertProvider>
					<TabsProvider>
						<PopUpProvider>
							<TypesProvider>
								{children}
							</TypesProvider>
						</PopUpProvider>
						</TabsProvider>
					</AlertProvider>
				</LocationProvider>
			</DarkProvider>
		</>
	);
}
