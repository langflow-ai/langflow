import { useContext, useEffect, useRef } from "react";
import { alertContext } from "../../contexts/alertContext";
import SingleAlert from "./components/singleAlertComponent";
import { AlertDropdownType } from "../../types/alerts";
import { PopUpContext } from "../../contexts/popUpContext";
import { useOnClickOutside } from "../hooks/useOnClickOutside";
import { X, Trash2 } from "lucide-react";

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
      className="z-10 flex h-[500px] w-[400px] flex-col overflow-hidden rounded-md bg-background px-2 py-3 pb-4 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"
    >
      <div className="text-md flex flex-row justify-between pl-3 font-medium text-foreground">
        Notifications
        <div className="flex gap-3 pr-3 ">
          <button
            className="text-foreground hover:text-status-red"
            onClick={() => {
              closePopUp();
              setTimeout(clearNotificationList, 100);
            }}
          >
            <Trash2 className="h-[1.1rem] w-[1.1rem]" />
          </button>
          <button
            className="text-foreground hover:text-status-red"
            onClick={closePopUp}
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>
      <div className="text-high-foreground mt-3 flex h-full w-full flex-col overflow-y-scroll scrollbar-hide">
        {notificationList.length !== 0 ? (
          notificationList.map((alertItem, index) => (
            <SingleAlert
              key={alertItem.id}
              dropItem={alertItem}
              removeAlert={removeFromNotificationList}
            />
          ))
        ) : (
          <div className="flex h-full w-full items-center justify-center pb-16 text-ring">
            No new notifications
          </div>
        )}
      </div>
    </div>
  );
}
