import { useEffect, useState } from "react";
import useAlertStore from "../../../../../../../../stores/alertStore";
import { gradients } from "../../../../../../../../utils/styleUtils";
import useGetProfilePictures from "./hooks/use-get-profile-pictures";
import { Label } from "../../../../../../../../components/ui/label";
import {
  BACKEND_URL,
  BASE_URL_API,
} from "../../../../../../../../constants/constants";
import HorizontalScrollFadeComponent from "../../../../../../../../components/horizontalScrollFadeComponent";
import LoadingComponent from "../../../../../../../../components/loadingComponent";
import Loading from "../../../../../../../../components/ui/loading";

export default function ProfilePictureChooserComponent({ value, onChange }) {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getProfilePictures = useGetProfilePictures({ setErrorData });

  const [profilePictures, setProfilePictures] = useState<string[][]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getProfilePictures()
      .then((data) => {
        if (data) {
          data.forEach((profile_picture) => {
            const [folder, path] = profile_picture.split("/");
            setProfilePictures((prev) => {
              if (prev[folder]) {
                prev[folder].push(path);
              } else {
                prev[folder] = [path];
              }
              return prev;
            });
            setLoading(false);
          });
        }
      })
      .catch(() => {
        setLoading(false);
      });
  });

  return (
    <div className="flex flex-col justify-center gap-2">
      {loading ? (
        <Loading />
      ) : (
        profilePictures.map((folder, idx) => (
          <Label>
            <div className="edit-flow-arrangement">
              <span className="font-medium">{folder}</span>
            </div>
            <HorizontalScrollFadeComponent>
              {folder.map((path, idx) => (
                <img
                  key={idx}
                  src={`${BACKEND_URL.slice(
                    0,
                    BACKEND_URL.length - 1,
                  )}${BASE_URL_API}files/images/${folder + "/" + path}`}
                  className={
                    "h-12 w-12 rounded-full" +
                    (value === folder + "/" + path
                      ? " border-2 border-white"
                      : "")
                  }
                  onClick={() => onChange(folder + "/" + path)}
                />
              ))}
            </HorizontalScrollFadeComponent>
          </Label>
        ))
      )}
    </div>
  );
}
