import { keepPreviousData } from "@tanstack/react-query";
import { profile } from "console";
import { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ProfilePicturesQueryParams {}

export interface ProfilePicturesResponse {
  files: string[];
}

export const useGetProfilePicturesQuery: useQueryFunctionType<
  ProfilePicturesQueryParams,
  ProfilePicturesResponse
> = () => {
  const { query } = UseRequestProcessor();

  const getProfilePicturesFn = async () => {
    const response = await api.get<ProfilePicturesResponse>(
      `${getURL("FILES")}/profile_pictures/list`,
    );

    return response.data;
  };

  const responseFn = async () => {
    const data = await getProfilePicturesFn();

    const profilePictures = {};

    data?.files?.forEach((profile_picture) => {
      const [folder, path] = profile_picture.split("/");

      if (profilePictures[folder]) {
        profilePictures[folder].push(path);
      } else {
        profilePictures[folder] = [path];
      }
    });

    return profilePictures;
  };

  const queryResult = query(["useGetProfilePicturesQuery"], responseFn, {
    placeholderData: keepPreviousData,
  });

  return queryResult;
};
