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
      className="z-10 flex h-[500px] w-[400px] flex-col overflow-hidden rounded-md bg-white px-2 py-3 pb-4 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none dark:bg-gray-800"
    >
      <div className="text-md flex flex-row justify-between pl-3 font-medium text-gray-800 dark:text-gray-200">
        Notifications
        <div className="flex gap-3 pr-3 ">
          <button
            className="text-gray-800 hover:text-red-500 dark:text-gray-200 dark:hover:text-red-500"
            onClick={() => {
              closePopUp();
              setTimeout(clearNotificationList, 100);
            }}
          >
            <TrashIcon className="h-[1.1rem] w-[1.1rem]" />
          </button>
          <button
            className="text-gray-800 hover:text-red-500 dark:text-gray-200 dark:hover:text-red-500"
            onClick={closePopUp}
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
      </div>
      <div className="mt-3 flex h-full w-full flex-col overflow-y-scroll text-gray-900 scrollbar-hide dark:text-gray-300">
        {notificationList.length !== 0 ? (
          notificationList.map((alertItem, index) => (
            <SingleAlert
              key={alertItem.id}
              dropItem={alertItem}
              removeAlert={removeFromNotificationList}
            />
          ))
        ) : (
          <div className="flex h-full w-full items-center justify-center pb-16 text-gray-500 dark:text-gray-500">
            No new notifications
          </div>
        )}
      </div>
    </div>
  );
}
