import * as Form from "@radix-ui/react-form";
import GradientChooserComponent from "../../../../../../components/gradientChooserComponent";
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

type ProfileGradientFormComponentProps = {
  gradient: string;
  handleInput: (event: any) => void;
  handlePatchGradient: (gradient: string) => void;
  userData: any;
};
const ProfileGradientFormComponent = ({
  gradient,
  handleInput,
  handlePatchGradient,
  userData,
}: ProfileGradientFormComponentProps) => {
  return (
    <>
      <Form.Root
        onSubmit={(event) => {
          handlePatchGradient(gradient);
          event.preventDefault();
        }}
      >
        <Card x-chunk="dashboard-04-chunk-1">
          <CardHeader>
            <CardTitle>Profile Gradient</CardTitle>
            <CardDescription>
              Choose the gradient that appears as your profile picture.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="py-2">
              <GradientChooserComponent
                value={
                  gradient == ""
                    ? (userData?.profile_image ??
                      gradients[
                        parseInt(userData?.id ?? "", 30) % gradients.length
                      ])
                    : gradient
                }
                onChange={(value) => {
                  handleInput({ target: { name: "gradient", value } });
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
    </>
  );
};
export default ProfileGradientFormComponent;
