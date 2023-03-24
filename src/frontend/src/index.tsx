import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import { BrowserRouter } from "react-router-dom";
import ContextWrapper from "./contexts";
import CrashErrorComponent from "./components/CrashErrorComponent";
import { ErrorBoundary } from "react-error-boundary";

const root = ReactDOM.createRoot(
	document.getElementById("root") as HTMLElement
);
root.render(
	<ContextWrapper>
		<BrowserRouter>

				<App />
		</BrowserRouter>
	</ContextWrapper>
);
reportWebVitals();
