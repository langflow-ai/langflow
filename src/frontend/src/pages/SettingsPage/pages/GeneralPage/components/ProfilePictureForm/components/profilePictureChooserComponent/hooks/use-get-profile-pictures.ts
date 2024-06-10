import axios from "axios";
import { PROFILE_PICTURES_GET_ERROR_ALERT } from "../../../../../../../../../constants/alerts_constants";
import { getProfilePictures } from "../../../../../../../../../controllers/API";

const useGetProfilePictures = (setErrorData) => {
  const handleGetProfilePictures = async () => {
    try {
      const profilePictures = await getProfilePictures();
      return profilePictures!.files;
    } catch (error) {
      if (axios.isCancel(error)) {
        console.warn("Request canceled: ", error.message);
      } else {
        setErrorData({
          title: PROFILE_PICTURES_GET_ERROR_ALERT,
          list: [(error as any)?.response?.data?.detail],
        });
      }
    }
  };

  return { handleGetProfilePictures };
};

export default useGetProfilePictures;
