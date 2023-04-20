import { ReactNode } from "react";
import { AlertProvider } from "./alertContext";
import { DarkProvider } from "./darkContext";
import { LocationProvider } from "./locationContext";
import PopUpProvider from "./popUpContext";
import { TabsProvider } from "./tabsContext";
import { TypesProvider } from "./typesContext";
import { TemplatesProvider } from "./templatesContext";

export default function ContextWrapper({ children }: { children: ReactNode }) {
	//element to wrap all context
	return (
		<>
			<DarkProvider>
				<LocationProvider>
					<AlertProvider>
						<TemplatesProvider>
							<TabsProvider>
								<PopUpProvider>
									<TypesProvider>{children}</TypesProvider>
								</PopUpProvider>
							</TabsProvider>
						</TemplatesProvider>
					</AlertProvider>
				</LocationProvider>
			</DarkProvider>
		</>
	);
}
