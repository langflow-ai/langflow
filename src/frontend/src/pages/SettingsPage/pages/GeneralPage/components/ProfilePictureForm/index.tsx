import {
  ProfilePicturesQueryResponse,
  useGetProfilePicturesQuery,
} from "@/controllers/API/queries/files";
import * as Form from "@radix-ui/react-form";
import { UseQueryResult } from "@tanstack/react-query";
import { Button } from "../../../../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../../../../../../components/ui/card";
import { gradients } from "../../../../../../utils/styleUtils";
import ProfilePictureChooserComponent from "./components/profilePictureChooserComponent";

type ProfilePictureFormComponentProps = {
  profilePicture: string;
  handleInput: (event: any) => void;
  handlePatchProfilePicture: (gradient: string) => void;
  handleGetProfilePictures: UseQueryResult<ProfilePicturesQueryResponse>;
  userData: any;
};
const ProfilePictureFormComponent = ({
  profilePicture,
  handleInput,
  handlePatchProfilePicture,
  handleGetProfilePictures,
  userData,
}: ProfilePictureFormComponentProps) => {
  const { isLoading, data, isFetching } = useGetProfilePicturesQuery();

  return (
    <Form.Root
      onSubmit={(event) => {
        handlePatchProfilePicture(profilePicture);
        event.preventDefault();
      }}
    >
      <Card x-chunk="dashboard-04-chunk-1">
        <CardHeader>
          <CardTitle>Profile Picture</CardTitle>
          <CardDescription>
            Choose the image that appears as your profile picture.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="py-2">
            <ProfilePictureChooserComponent
              profilePictures={data}
              loading={isLoading || isFetching}
              value={
                profilePicture == ""
                  ? (userData?.profile_image ??
                    gradients[
                      parseInt(userData?.id ?? "", 30) % gradients.length
                    ])
                  : profilePicture
              }
              onChange={(value) => {
                handleInput({ target: { name: "profilePicture", value } });
              }}
            />
          </div>
        </CardContent>
        <CardFooter className="border-t px-6 py-4">
          <Form.Submit asChild>
            <Button type="submit">Save</Button>
          </Form.Submit>
        </CardFooter>
      </Card>
    </Form.Root>
  );
};
export default ProfilePictureFormComponent;
