import useAlertStore from "../../stores/alertStore";
import SingleAlert from "../alertDropDown/components/singleAlertComponent";
import ErrorAlert from "../error";
import NoticeAlert from "../notice";
import SuccessAlert from "../success";

export default function AlertDisplayArea() {
  const removeFromTempNotificationList = useAlertStore(
    (state) => state.removeFromTempNotificationList,
  );
  const tempNotificationList = useAlertStore(
    (state) => state.tempNotificationList,
  );
  const removeAlert = (id: string) => {
    removeFromTempNotificationList(id);
  };

  return (
    <div className="flex flex-col-reverse" style={{ zIndex: 999 }}>
      {tempNotificationList.map((alert) => (
        <div key={alert.id}>
          <SingleAlert
            dropItem={alert}
            removeAlert={removeAlert}
            isDropdown={false}
          />
        </div>
      ))}
    </div>
  );
}
