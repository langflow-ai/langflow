import {
  EDIT_PASSWORD_ALERT_LIST,
  EDIT_PASSWORD_ERROR_ALERT,
  SAVE_ERROR_ALERT,
  SAVE_SUCCESS_ALERT,
} from "../../../../constants/alerts_constants";
import { resetPassword } from "../../../../controllers/API";
import { Users } from "../../../../types/api";

const usePatchPassword = (
  userData: Users | null,
  setSuccessData: (data: { title: string; list?: string[] }) => void,
  setErrorData: (data: { title: string; list: string[] }) => void,
) => {
  const handlePatchPassword = async (password, cnfPassword, handleInput) => {
    if (password !== cnfPassword) {
      setErrorData({
        title: EDIT_PASSWORD_ERROR_ALERT,
        list: [EDIT_PASSWORD_ALERT_LIST],
      });
      return;
    }
    try {
      if (password !== "") await resetPassword(userData!.id, { password });
      handleInput({ target: { name: "password", value: "" } });
      handleInput({ target: { name: "cnfPassword", value: "" } });
      setSuccessData({ title: SAVE_SUCCESS_ALERT });
    } catch (error) {
      setErrorData({
        title: SAVE_ERROR_ALERT,
        list: [(error as any)?.response?.data?.detail],
      });
    }
  };

  return {
    handlePatchPassword,
  };
};

export default usePatchPassword;
