import ProfilePictureChooserComponent, {
  type ProfilePictureChooserComponentProps,
} from "@/pages/SettingsPage/pages/GeneralPage/components/ProfilePictureForm/components/profilePictureChooserComponent";
export function CustomProfilePictureChooserComponent({
  profilePictures,
  loading,
  value,
  onChange,
}: ProfilePictureChooserComponentProps) {
  return (
    <ProfilePictureChooserComponent
      profilePictures={profilePictures}
      loading={loading}
      value={value}
      onChange={onChange}
    />
  );
}

export default CustomProfilePictureChooserComponent;
