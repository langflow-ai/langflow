import { useEffect } from "react";
import {
  BACKEND_URL,
  BASE_URL_API,
} from "../../../../../../../../../constants/constants";

const usePreloadImages = (
  profilePictures: { [key: string]: string[] },
  setImagesLoaded: (value: boolean) => void,
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
    const imageArray: string[] = [];
    const firstUrl = `${BACKEND_URL.slice(0, BACKEND_URL.length - 1)}`;

    Object.keys(profilePictures).flatMap((folder) =>
      profilePictures[folder].map((path) =>
        imageArray.push(
          `${firstUrl}${BASE_URL_API}files/profile_pictures/${folder}/${path}`,
        ),
      ),
    );

    preloadImages(imageArray).then(() => {
      setImagesLoaded(true);
    });
  }, [profilePictures]);

  return;
};

export default usePreloadImages;
