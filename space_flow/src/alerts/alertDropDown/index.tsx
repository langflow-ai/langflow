import { useContext } from "react";
import { alertContext } from "../../contexts/alertContext";
import {
  CheckCircleIcon,
  InformationCircleIcon,
  XCircleIcon,
  XMarkIcon,
} from "@heroicons/react/24/solid";
import { Link } from "react-router-dom";
import { Transition } from "@headlessui/react";
import { TrashIcon } from "@heroicons/react/24/outline";
import SingleAlert from "./components/singleAlertComponent";

type AlertDropdownProps = {
  closeFunction: () => void;
  open?: boolean;
};

export type alertDropdownItem = {
  type: "notice" | "error" | "success";
  title: string;
  link?: string;
  list?: Array<string>;
  id: string;
};

export default function AlertDropdown({closeFunction, open}: AlertDropdownProps) {
  const {
    notificationList,
    clearNotificationList,
    removeFromNotificationList,
  } = useContext(alertContext);

  

  return (
    <Transition
      show={open}
      enter="transition ease-out duration-100"
      enterFrom="transform opacity-0 scale-95"
      enterTo="transform opacity-100 scale-100"
      leave="transition ease-in duration-75"
      leaveFrom="transform opacity-100 scale-100"
      leaveTo="transform opacity-0 scale-95"
    >
      <div className="z-10 px-8 py-6 pb-8 rounded-md bg-white ring-1 ring-black ring-opacity-5 shadow-lg focus:outline-none overflow-hidden w-[36rem] h-[40rem] flex flex-col">
        <div className="flex flex-row justify-between text-md font-medium text-gray-800">
          Notifications
          <div className="flex gap-4">
            <button
              className="hover:text-black"
              onClick={() => {closeFunction(); setTimeout(clearNotificationList, 100)}}
            >
              <TrashIcon className="w-5 h-5" />
            </button>
            <button
              className="hover:text-black"
              onClick={closeFunction}
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
        </div>
        <div className="mt-6 flex flex-col overflow-y-scroll w-full h-full scrollbar-hide">
          {notificationList.length !== 0 ? 
          notificationList.map((alertItem, index) => (
            <SingleAlert key={index} dropItem={alertItem} removeAlert={removeFromNotificationList} />
          ))
        :
        <div className="h-full w-full pb-16 text-slate-500 flex justify-center items-center">
          No new notifications
          </div>
        }
        </div>
      </div>
    </Transition>
  );
}
