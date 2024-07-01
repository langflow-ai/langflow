import { postLikeComponent } from "../../../controllers/API";
import { storeComponent } from "../../../types/store";

const useLikeComponent = (
  data: storeComponent,
  name: string,
  setLoadingLike: (value: boolean) => void,
  likedByUser: boolean | null | undefined,
  likesCount: number,
  setLikedByUser: (value: any) => void,
  setLikesCount: (value: any) => void,
  setValidApiKey: (value: boolean) => void,
  setErrorData: (value: { title: string; list: string[] }) => void,
) => {
  const handleLike = () => {
    setLoadingLike(true);
    if (likedByUser !== undefined || likedByUser !== null) {
      const temp = likedByUser;
      const tempNum = likesCount;
      setLikedByUser((prev) => !prev);
      setLikesCount((prev) => (temp ? prev - 1 : prev + 1));

      postLikeComponent(data.id)
        .then((response) => {
          setLoadingLike(false);
          setLikesCount(response.data.likes_count);
          setLikedByUser(response.data.liked_by_user);
        })
        .catch((error) => {
          setLoadingLike(false);
          setLikesCount(tempNum);
          setLikedByUser(temp);
          if (error.response.status === 403) {
            setValidApiKey(false);
          } else {
            console.error(error);
            setErrorData({
              title: `Error liking ${name}.`,
              list: [error.response.data.detail],
            });
          }
        });
    }
  };

  return {
    handleLike,
  };
};

export default useLikeComponent;
