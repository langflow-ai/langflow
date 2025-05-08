import { useGetBasicExamplesQuery } from "@/controllers/API/queries/flows/use-get-basic-examples";
import { useGetTypes } from "@/controllers/API/queries/flows/use-get-types";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import { useGetTagsQuery } from "@/controllers/API/queries/store";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { useCustomPostAuth } from "@/customization/hooks/use-custom-post-auth";
import { Outlet } from "react-router-dom";
import { LoadingPage } from "../LoadingPage";

export function AppAuthenticatedPage() {
  useCustomPostAuth();

  // Now that we're authenticated, fetch all the required data
  const { isFetched: typesLoaded } = useGetTypes({ enabled: true });
  useGetGlobalVariables({ enabled: typesLoaded });
  useGetTagsQuery({ enabled: typesLoaded });
  useGetFoldersQuery({
    enabled: typesLoaded,
  });
  const { isFetched: isExamplesFetched } = useGetBasicExamplesQuery({
    enabled: typesLoaded,
  });

  // Only render the content when all data is loaded
  if (!typesLoaded || !isExamplesFetched) {
    return <LoadingPage overlay />;
  }

  return <Outlet />;
}
