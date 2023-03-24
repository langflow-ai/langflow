import "reactflow/dist/style.css";
import { useState, useEffect, useContext } from "react";
import "./App.css";
import { useLocation } from "react-router-dom";
import ErrorAlert from "./alerts/error";
import NoticeAlert from "./alerts/notice";
import SuccessAlert from "./alerts/success";
import ExtraSidebar from "./components/ExtraSidebarComponent";
import { alertContext } from "./contexts/alertContext";
import { locationContext } from "./contexts/locationContext";
import TabsManagerComponent from "./pages/FlowPage/components/tabsManagerComponent";
import { ErrorBoundary } from "react-error-boundary";
import CrashErrorComponent from "./components/CrashErrorComponent";
import { TabsContext } from "./contexts/tabsContext";

export default function App() {
	var _ = require("lodash");

	let { setCurrent, setShowSideBar, setIsStackedOpen } =
		useContext(locationContext);
	let location = useLocation();
	useEffect(() => {
		setCurrent(location.pathname.replace(/\/$/g, "").split("/"));
		setShowSideBar(true);
		setIsStackedOpen(true);
	}, [location.pathname, setCurrent, setIsStackedOpen, setShowSideBar]);
	const {hardReset} = useContext(TabsContext)
	const {
		errorData,
		errorOpen,
		setErrorOpen,
		noticeData,
		noticeOpen,
		setNoticeOpen,
		successData,
		successOpen,
		setSuccessOpen,
	} = useContext(alertContext);

	// Initialize state variable for the list of alerts
	const [alertsList, setAlertsList] = useState<
		Array<{
			type: string;
			data: { title: string; list?: Array<string>; link?: string };
			id: string;
		}>
	>([]);

	// Use effect hook to update alertsList when a new alert is added
	useEffect(() => {
		// If there is an error alert open with data, add it to the alertsList
		if (errorOpen && errorData) {
			setErrorOpen(false);
			setAlertsList((old) => {
				let newAlertsList = [
					...old,
					{ type: "error", data: _.cloneDeep(errorData), id: _.uniqueId() },
				];
				return newAlertsList;
			});
		}
		// If there is a notice alert open with data, add it to the alertsList
		else if (noticeOpen && noticeData) {
			setNoticeOpen(false);
			setAlertsList((old) => {
				let newAlertsList = [
					...old,
					{ type: "notice", data: _.cloneDeep(noticeData), id: _.uniqueId() },
				];
				return newAlertsList;
			});
		}
		// If there is a success alert open with data, add it to the alertsList
		else if (successOpen && successData) {
			setSuccessOpen(false);
			setAlertsList((old) => {
				let newAlertsList = [
					...old,
					{ type: "success", data: _.cloneDeep(successData), id: _.uniqueId() },
				];
				return newAlertsList;
			});
		}
	}, [
		_,
		errorData,
		errorOpen,
		noticeData,
		noticeOpen,
		setErrorOpen,
		setNoticeOpen,
		setSuccessOpen,
		successData,
		successOpen,
	]);

	const removeAlert = (id: string) => {
		setAlertsList((prevAlertsList) =>
			prevAlertsList.filter((alert) => alert.id !== id)
		);
	};

	return (
		//need parent component with width and height
		<div className="h-full flex flex-col">
			<div className="flex grow-0 shrink basis-auto"></div>
			<ErrorBoundary
				onReset={() => {
					window.localStorage.removeItem("tabsData");
					window.localStorage.clear();
					hardReset()
					window.location.href = window.location.href;
				}}
				FallbackComponent={CrashErrorComponent}
			>
				<div className="flex grow shrink basis-auto min-h-0 flex-1 overflow-hidden">
					<ExtraSidebar />
					{/* Main area */}
					<main className="min-w-0 flex-1 border-t border-gray-200 dark:border-gray-700 flex">
						{/* Primary column */}
						<div className="w-full h-full">
							<TabsManagerComponent></TabsManagerComponent>
						</div>
					</main>
				</div>
			</ErrorBoundary>
			<div></div>
			<div className="flex z-40 flex-col-reverse fixed bottom-5 left-5">
				{alertsList.map((alert) => (
					<div key={alert.id}>
						{alert.type === "error" ? (
							<ErrorAlert
								key={alert.id}
								title={alert.data.title}
								list={alert.data.list}
								id={alert.id}
								removeAlert={removeAlert}
							/>
						) : alert.type === "notice" ? (
							<NoticeAlert
								key={alert.id}
								title={alert.data.title}
								link={alert.data.link}
								id={alert.id}
								removeAlert={removeAlert}
							/>
						) : (
							<SuccessAlert
								key={alert.id}
								title={alert.data.title}
								id={alert.id}
								removeAlert={removeAlert}
							/>
						)}
					</div>
				))}
			</div>
			<a
				target={"_blank"}
				href="https://logspace.ai/"
				className="absolute bottom-1 left-1 text-gray-500 text-xs cursor-pointer font-sans tracking-wide"
			>
				Created by Logspace
			</a>
		</div>
	);
}
