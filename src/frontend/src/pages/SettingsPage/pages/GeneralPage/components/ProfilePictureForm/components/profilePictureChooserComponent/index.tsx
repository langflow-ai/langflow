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

type ProfilePictureChooserComponentProps = {
  profilePictures: { [key: string]: string[] };
  loading: boolean;
  value: string;
  onChange: (value: string) => void;
};

export default function ProfilePictureChooserComponent({
  profilePictures,
  loading,
  value,
  onChange,
}: ProfilePictureChooserComponentProps) {
  return (
    <div className="flex flex-col justify-center gap-2">
      {loading ? (
        <Loading />
      ) : (
        Object.keys(profilePictures).map((folder, idx) => (
          <Label>
            <div className="edit-flow-arrangement">
              <span className="font-medium">{folder}</span>
            </div>
            <HorizontalScrollFadeComponent>
              {profilePictures[folder].map((path, idx) => (
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
