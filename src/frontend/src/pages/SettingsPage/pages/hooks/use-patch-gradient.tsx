import cloneDeep from "lodash/cloneDeep";
import {
  SAVE_ERROR_ALERT,
  SAVE_SUCCESS_ALERT,
} from "../../../../constants/alerts_constants";
import { updateUser } from "../../../../controllers/API";

const usePatchGradient = (
  setSuccessData,
  setErrorData,
  currentUserData,
  setUserData,
) => {
  const handlePatchGradient = async (gradient) => {
    try {
      if (gradient !== "") {
        await updateUser(currentUserData.id, { profile_image: gradient });
        let newUserData = cloneDeep(currentUserData);
        newUserData.profile_image = gradient;
        setUserData(newUserData);
      }
      setSuccessData({ title: SAVE_SUCCESS_ALERT });
    } catch (error) {
      setErrorData({
        title: SAVE_ERROR_ALERT,
        list: [(error as any)?.response?.data?.detail],
      });
    }
  };

  return {
    currentUserData,
    handlePatchGradient,
  };
};

export default usePatchGradient;
