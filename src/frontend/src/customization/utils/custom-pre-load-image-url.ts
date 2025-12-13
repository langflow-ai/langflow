import { getBaseUrl } from "@/customization/utils/urls";

export const customPreLoadImageUrl = (imageUrl: string) => {
  return `${getBaseUrl()}files/profile_pictures/${imageUrl}`;
};
