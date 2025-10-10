import { BASE_URL_API } from "@/constants/constants";

export const customPreLoadImageUrl = (imageUrl: string) => {
  return `${BASE_URL_API}files/profile_pictures/${imageUrl}`;
};
