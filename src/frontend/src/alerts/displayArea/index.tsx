import useAlertStore from "../../stores/alertStore";
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
          {alert.type === "error" ? (
            <ErrorAlert
              key={alert.id}
              title={alert.title}
              list={alert.list}
              id={alert.id}
              removeAlert={removeAlert}
            />
          ) : alert.type === "notice" ? (
            <NoticeAlert
              key={alert.id}
              title={alert.title}
              link={alert.link}
              id={alert.id}
              removeAlert={removeAlert}
            />
          ) : (
            alert.type === "success" && (
              <SuccessAlert
                key={alert.id}
                title={alert.title}
                id={alert.id}
                removeAlert={removeAlert}
              />
            )
          )}
        </div>
      ))}
    </div>
  );
}
