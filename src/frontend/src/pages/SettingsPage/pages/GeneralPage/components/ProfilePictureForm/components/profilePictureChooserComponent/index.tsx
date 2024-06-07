import { useEffect, useState } from "react";
import useAlertStore from "../../../../../../../../stores/alertStore";
import { gradients } from "../../../../../../../../utils/styleUtils";
import useGetProfilePictures from "./hooks/use-get-profile-pictures";
import { Label } from "../../../../../../../../components/ui/label";
import {
  BACKEND_URL,
  BASE_URL_API,
} from "../../../../../../../../constants/constants";

export default function ProfilePictureChooserComponent({ value, onChange }) {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getProfilePictures = useGetProfilePictures({ setErrorData });

  const [profilePictures, setProfilePictures] = useState<string[][]>([]);

  useEffect(() => {
    getProfilePictures().then((data) => {
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
        });
      }
    });
  });

  return (
    <div className="flex flex-wrap items-center justify-start gap-2">
      {profilePictures.map((folder, idx) => (
        <Label>
          <div className="edit-flow-arrangement">
            <span className="font-medium">{folder}</span>
          </div>
          <div className="flex flex-wrap items-center justify-start gap-2">
            {folder.map((path, idx) => (
              <img
                key={idx}
                src={`${BACKEND_URL.slice(
                  0,
                  BACKEND_URL.length - 1,
                )}${BASE_URL_API}files/images/${folder + "/" + path}`}
                className="h-12 w-12 rounded-full"
                onClick={() => onChange(folder + "/" + path)}
              />
            ))}
          </div>
        </Label>
      ))}
    </div>
  );
}
