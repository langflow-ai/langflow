import { Dialog, Transition } from "@headlessui/react";
import {
	XMarkIcon,
	ArrowDownTrayIcon,
	DocumentDuplicateIcon,
    ComputerDesktopIcon,
	ArrowUpTrayIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import ButtonBox from "./buttonBox";

export default function ImportModal() {
	const [open, setOpen] = useState(true);
	const { closePopUp } = useContext(PopUpContext);
	const ref = useRef();
    const {uploadFlow} = useContext(TabsContext)
	function setModalOpen(x: boolean) {
		setOpen(x);
		if (x === false) {
			setTimeout(() => {
				closePopUp();
			}, 300);
		}
	}
	return (
		<Transition.Root show={open} appear={true} as={Fragment}>
			<Dialog
				as="div"
				className="relative z-10"
				onClose={setModalOpen}
				initialFocus={ref}
			>
				<Transition.Child
					as={Fragment}
					enter="ease-out duration-300"
					enterFrom="opacity-0"
					enterTo="opacity-100"
					leave="ease-in duration-200"
					leaveFrom="opacity-100"
					leaveTo="opacity-0"
				>
					<div className="fixed inset-0 bg-gray-500 dark:bg-gray-600 dark:bg-opacity-75 bg-opacity-75 transition-opacity" />
				</Transition.Child>

				<div className="fixed inset-0 z-10 overflow-y-auto">
					<div className="flex h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
						<Transition.Child
							as={Fragment}
							enter="ease-out duration-300"
							enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
							enterTo="opacity-100 translate-y-0 sm:scale-100"
							leave="ease-in duration-200"
							leaveFrom="opacity-100 translate-y-0 sm:scale-100"
							leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
						>
							<Dialog.Panel className="relative flex flex-col justify-between transform h-[600px] overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-left shadow-xl transition-all sm:my-8 w-[700px]">
								<div className=" z-50 absolute top-0 right-0 hidden pt-4 pr-4 sm:block">
									<button
										type="button"
										className="rounded-md text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
										onClick={() => {
											setModalOpen(false);
										}}
									>
										<span className="sr-only">Close</span>
										<XMarkIcon className="h-6 w-6" aria-hidden="true" />
									</button>
								</div>
								<div className="h-full w-full flex flex-col justify-center items-center">
									<div className="flex w-full pb-4 z-10 justify-center shadow-sm">
										<div className="mx-auto mt-4 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-gray-900 sm:mx-0 sm:h-10 sm:w-10">
											<ArrowUpTrayIcon
												className="h-6 w-6 text-blue-600"
												aria-hidden="true"
											/>
										</div>
										<div className="mt-4 text-center sm:ml-4 sm:text-left">
											<Dialog.Title
												as="h3"
												className="text-lg font-medium dark:text-white leading-10 text-gray-900"
											>
												Import from
											</Dialog.Title>
										</div>
									</div>
									<div className="h-full w-full bg-gray-200 dark:bg-gray-900 p-4 gap-4 flex flex-row justify-center items-center">
										<div className="flex h-full w-full justify-evenly items-center">
											<ButtonBox
												deactivate
												bgColor="bg-slate-400"
												description="Prebuilt Examples"
												icon={
													<DocumentDuplicateIcon className="h-10 w-10 flex-shrink-0" />
												}
												onClick={() => console.log("sdsds")}
												textColor="text-slate-400"
												title="Examples"
											></ButtonBox>
											<ButtonBox
												bgColor="bg-blue-500"
												description="Import from Local"
												icon={
													<ComputerDesktopIcon className="h-10 w-10 flex-shrink-0" />
												}
												onClick={() => {uploadFlow();setModalOpen(false)}}
												textColor="text-blue-500"
												title="Local file"
											></ButtonBox>
										</div>
									</div>

								</div>
							</Dialog.Panel>
						</Transition.Child>
					</div>
				</div>
			</Dialog>
		</Transition.Root>
	);
}
