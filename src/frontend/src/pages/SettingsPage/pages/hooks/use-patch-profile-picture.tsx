import cloneDeep from "lodash/cloneDeep";
import {
  SAVE_ERROR_ALERT,
  SAVE_SUCCESS_ALERT,
} from "../../../../constants/alerts_constants";
import { updateUser } from "../../../../controllers/API";
import { Users } from "../../../../types/api";

const usePatchProfilePicture = (
  setSuccessData: (data: { title: string; list?: string[] }) => void,
  setErrorData: (data: { title: string; list: string[] }) => void,
  currentUserData: Users | null,
  setUserData: (data: any) => void,
) => {
  const handlePatchProfilePicture = async (profile_picture) => {
    try {
      if (profile_picture !== "") {
        await updateUser(currentUserData!.id, {
          profile_image: profile_picture,
        });
        let newUserData = cloneDeep(currentUserData);
        newUserData!.profile_image = profile_picture;
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
    handlePatchProfilePicture,
  };
};

export default usePatchProfilePicture;
