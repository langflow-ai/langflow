import { reject } from "lodash";
import { PROFILE_PICTURES_GET_ERROR_ALERT } from "../../../../../../../../../constants/alerts_constants";
import { getProfilePictures } from "../../../../../../../../../controllers/API";

const useGetProfilePictures = (setErrorData) => {
  const handleGetProfilePictures = async () => {
    try {
      const profilePictures = await getProfilePictures();
      return profilePictures.files;
    } catch (error) {
      setErrorData({
        title: PROFILE_PICTURES_GET_ERROR_ALERT,
        list: [(error as any)?.response?.data?.detail],
      });
      throw error;
    }
  };

  return handleGetProfilePictures;
};

export default useGetProfilePictures;
