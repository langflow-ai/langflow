import useAlertStore from "../../../../../../../../stores/alertStore";
import { gradients } from "../../../../../../../../utils/styleUtils";
import useGetProfilePictures from "./hooks/use-get-profile-pictures";

export default function ProfilePictureChooserComponent({ value, onChange }) {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getProfilePictures = useGetProfilePictures({ setErrorData });

  return (
    <div className="flex flex-wrap items-center justify-start gap-2">
      {gradients.map((gradient, idx) => (
        <div
          onClick={() => {
            onChange(gradient);
          }}
          className={
            "duration-400 h-12 w-12 cursor-pointer rounded-full transition-all " +
            gradient +
            (value === gradient ? " shadow-lg ring-2 ring-primary" : "")
          }
          key={idx}
        ></div>
      ))}
    </div>
  );
}
