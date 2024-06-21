import { useEffect } from "react";

const useDataEffect = (
  data,
  setLikedByUser,
  setLikesCount,
  setDownloadsCount,
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
