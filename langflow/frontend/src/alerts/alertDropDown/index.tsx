import { useContext } from "react";
import { alertContext } from "../../contexts/alertContext";
import {
  XMarkIcon,
} from "@heroicons/react/24/solid";
import { TrashIcon } from "@heroicons/react/24/outline";
import SingleAlert from "./components/singleAlertComponent";
import { AlertDropdownType } from "../../types/alerts";
import { PopUpContext } from "../../contexts/popUpContext";



export default function AlertDropdown({}: AlertDropdownType) {
  const {
    notificationList,
    clearNotificationList,
    removeFromNotificationList,
  } = useContext(alertContext);
  const {closePopUp} =  useContext(PopUpContext)
  

  return (
      <div className="z-10 py-2 pb-4 rounded-md bg-white ring-1 ring-black ring-opacity-5 shadow-lg focus:outline-none overflow-hidden w-[14rem] h-[28rem] flex flex-col">
        <div className="flex pl-3 flex-row justify-between text-md font-medium text-gray-800">
          Notifications
          <div className="flex gap-3 pr-2 ">
            <button
              className="hover:text-black"
              onClick={() => {closePopUp(); setTimeout(clearNotificationList, 100)}}
            >
              <TrashIcon className="w-5 h-5" />
            </button>
            <button
              className="hover:text-black"
              onClick={closePopUp}
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
        </div>
        <div className="mt-2 flex flex-col overflow-y-scroll w-full h-full scrollbar-hide">
          {notificationList.length !== 0 ? 
          notificationList.map((alertItem, index) => (
            <SingleAlert key={alertItem.id} dropItem={alertItem} removeAlert={removeFromNotificationList} />
          ))
        :
        <div className="h-full w-full pb-16 text-gray-500 flex justify-center items-center">
          No new notifications
          </div>
        }
        </div>
      </div>
  );
}
