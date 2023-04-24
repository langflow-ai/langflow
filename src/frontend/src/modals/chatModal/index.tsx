import { Dialog, Transition } from "@headlessui/react";
import {
	XMarkIcon,
	ClipboardDocumentListIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";

export default function ChatModal() {
	const [open, setOpen] = useState(true);
	const { closePopUp } = useContext(PopUpContext);
	const ref = useRef();
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
								<div className="h-full w-full flex flex-col justify-center items-center">
									<div className="h-full w-full bg-white dark:bg-gray-900 p-4 gap-4 flex flex-row justify-center items-center">
									</div>
                                    <div>input area</div>
								</div>
							</Dialog.Panel>
						</Transition.Child>
					</div>
				</div>
			</Dialog>
		</Transition.Root>
	);
}
