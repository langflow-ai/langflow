import { AlertComponentType } from "../../../../types/alerts";
import ErrorAlertComponent from "../errorAlertComponent";
import NoticeAlertComponent from "../noticeAlertComponent";
import SuccessAlertComponent from "../successAlertComponent";

export default function RenderAlertComponent({
  alert,
  setShow,
  removeAlert,
  isDropdown,
}: AlertComponentType): JSX.Element {

  const Alerts = {
    error: ErrorAlertComponent,
    notice: NoticeAlertComponent,
    success: SuccessAlertComponent
  }

  const AlertComponent = Alerts[alert.type];

  return (
    <AlertComponent
      alert={alert}
      setShow={setShow}
      removeAlert={removeAlert}
      isDropdown={isDropdown}
    />
  );
}
