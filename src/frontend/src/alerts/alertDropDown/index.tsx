import { useContext, useEffect, useRef } from "react";
import { alertContext } from "../../contexts/alertContext";
import { XMarkIcon } from "@heroicons/react/24/solid";
import { TrashIcon } from "@heroicons/react/24/outline";
import SingleAlert from "./components/singleAlertComponent";
import { AlertDropdownType } from "../../types/alerts";
import { PopUpContext } from "../../contexts/popUpContext";
import { useOnClickOutside } from "../hooks/useOnClickOutside";
export default function AlertDropdown({}: AlertDropdownType) {
  const { closePopUp } = useContext(PopUpContext);
  const componentRef = useRef<HTMLDivElement>(null);

  // Use the custom hook
  useOnClickOutside(componentRef, () => {
    closePopUp();
  });

  const {
    notificationList,
    clearNotificationList,
    removeFromNotificationList,
  } = useContext(alertContext);

  return (
    <div
      ref={componentRef}
      className="z-10 py-3 pb-4 px-2 rounded-md bg-white dark:bg-gray-800 ring-1 ring-black ring-opacity-5 shadow-lg focus:outline-none overflow-hidden w-[400px] h-[500px] flex flex-col"
    >
      <div className="flex pl-3 flex-row justify-between text-md font-medium text-gray-800 dark:text-gray-200">
        Notifications
        <div className="flex gap-3 pr-3 ">
          <button
            className="text-gray-800 hover:text-red-500 dark:text-gray-200 dark:hover:text-red-500"
            onClick={() => {
              closePopUp();
              setTimeout(clearNotificationList, 100);
            }}
          >
            <TrashIcon className="w-[1.1rem] h-[1.1rem]" />
          </button>
          <button
            className="text-gray-800 hover:text-red-500 dark:text-gray-200 dark:hover:text-red-500"
            onClick={closePopUp}
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
      </div>
      <div className="mt-3 flex flex-col overflow-y-scroll w-full h-full scrollbar-hide text-gray-900 dark:text-gray-300">
        {notificationList.length !== 0 ? (
          notificationList.map((alertItem, index) => (
            <SingleAlert
              key={alertItem.id}
              dropItem={alertItem}
              removeAlert={removeFromNotificationList}
            />
          ))
        ) : (
          <div className="h-full w-full pb-16 text-gray-500 dark:text-gray-500 flex justify-center items-center">
            No new notifications
          </div>
        )}
      </div>
    </div>
  );
}
