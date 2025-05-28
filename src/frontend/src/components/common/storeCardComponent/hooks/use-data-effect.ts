import { useEffect } from "react";
import { storeComponent } from "../../../../types/store";

const useDataEffect = (
  data: storeComponent,
  setLikedByUser: (value: any) => void,
  setLikesCount: (value: any) => void,
  setDownloadsCount: (value: any) => void,
) => {
  useEffect(() => {
    if (data) {
      setLikedByUser(data?.liked_by_user ?? false);
      setLikesCount(data?.liked_by_count ?? 0);
      setDownloadsCount(data?.downloads_count ?? 0);
    }
  }, [data, data?.liked_by_count, data?.liked_by_user, data?.downloads_count]);
};

export default useDataEffect;
