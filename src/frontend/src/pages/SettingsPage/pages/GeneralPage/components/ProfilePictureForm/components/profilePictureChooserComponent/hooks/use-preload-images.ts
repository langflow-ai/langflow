import { ENABLE_LANGFLOW_DESKTOP } from "@/customization/feature-flags";
import { useEffect } from "react";
import {
  BASE_URL_API,
  baseURL,
} from "../../../../../../../../../constants/constants";

const usePreloadImages = (
  setImagesLoaded: (value: boolean) => void,
  loading: boolean,
  profilePictures?: { [key: string]: string[] },
) => {
  const preloadImages = async (imageUrls) => {
    return Promise.all(
      imageUrls.map(
        (src) =>
          new Promise((resolve) => {
            const img = new Image();
            img.src = src;
            img.onload = resolve;
            img.onerror = resolve;
          }),
      ),
    );
  };

  useEffect(() => {
    if (loading || !profilePictures) return;
    const imageArray: string[] = [];

    Object.keys(profilePictures).flatMap((folder) =>
      profilePictures[folder].map((path) =>
        imageArray.push(
          `${ENABLE_LANGFLOW_DESKTOP ? baseURL : ""}${BASE_URL_API}files/profile_pictures/${folder}/${path}`,
        ),
      ),
    );

    preloadImages(imageArray).then(() => {
      setImagesLoaded(true);
    });
  }, [profilePictures, loading]);

  return;
};

export default usePreloadImages;
