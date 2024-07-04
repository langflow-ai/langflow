import { keepPreviousData } from "@tanstack/react-query";
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

  const queryResult = query(
    ["useGetProfilePicturesQuery"],
    getProfilePicturesFn,
    {
      placeholderData: keepPreviousData,
    },
  );

  return queryResult;
};
