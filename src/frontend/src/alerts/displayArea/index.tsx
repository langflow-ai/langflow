import { useTranslation } from "react-i18next";
import useAlertStore from "../../stores/alertStore";
import ErrorAlert from "../error";
import NoticeAlert from "../notice";
import SuccessAlert from "../success";

export default function AlertDisplayArea() {
  const { t } = useTranslation();
  const removeFromTempNotificationList = useAlertStore(
    (state) => state.removeFromTempNotificationList,
  );
  const tempNotificationList = useAlertStore(
    (state) => state.tempNotificationList,
  );
  const removeAlert = (id: string) => {
    removeFromTempNotificationList(id);
  };
  const errorAlerts = tempNotificationList.filter(
    (alert) => alert.type === "error",
  );
  const politeAlerts = tempNotificationList.filter(
    (alert) => alert.type !== "error",
  );

  return (
    <div
      role="region"
      aria-label={t("alerts.notificationsTitle")}
      style={{ zIndex: 999 }}
    >
      <div
        aria-atomic="true"
        aria-live="assertive"
        className="flex flex-col-reverse"
      >
        {errorAlerts.map((alert) => (
          <div key={alert.id} role="alert">
            <ErrorAlert
              title={alert.title}
              list={alert.list}
              id={alert.id}
              removeAlert={removeAlert}
            />
          </div>
        ))}
      </div>
      <div
        aria-atomic="true"
        aria-live="polite"
        className="flex flex-col-reverse"
        role="status"
      >
        {politeAlerts.map((alert) =>
          alert.type === "notice" ? (
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
          ),
        )}
      </div>
    </div>
  );
}
