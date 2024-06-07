import { reject } from "lodash";
import { PROFILE_PICTURES_GET_ERROR_ALERT } from "../../../../../../../../../constants/alerts_constants";
import { getProfilePictures } from "../../../../../../../../../controllers/API";

const useGetProfilePictures = (setErrorData) => {
  const handleGetProfilePictures = async (abortSignal) => {
    try {
      const profilePictures = await getProfilePictures(abortSignal);
      return profilePictures!.files;
    } catch (error) {
      console.log(error);
      setErrorData({
        title: PROFILE_PICTURES_GET_ERROR_ALERT,
        list: [(error as any)?.response?.data?.detail],
      });
      throw error;
    }
  };

  return { handleGetProfilePictures };
};

export default useGetProfilePictures;
