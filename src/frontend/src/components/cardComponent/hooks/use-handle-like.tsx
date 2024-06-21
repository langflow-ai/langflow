import { postLikeComponent } from "../../../controllers/API";

const useLikeComponent = (
  data,
  name,
  setLoadingLike,
  likedByUser,
  likesCount,
  setLikedByUser,
  setLikesCount,
  setValidApiKey,
  setErrorData,
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
