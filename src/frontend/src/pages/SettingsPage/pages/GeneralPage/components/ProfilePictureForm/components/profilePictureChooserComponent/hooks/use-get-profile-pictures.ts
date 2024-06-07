import { PROFILE_PICTURES_GET_ERROR_ALERT } from "../../../../../../../../../constants/alerts_constants";

const useGetProfilePictures = (setErrorData) => {
  const handleGetProfilePictures = async () => {
    try {
    } catch (error) {
      setErrorData({
        title: PROFILE_PICTURES_GET_ERROR_ALERT,
        list: [(error as any)?.response?.data?.detail],
      });
    }
  };

  return handleGetProfilePictures;
};

export default useGetProfilePictures;
