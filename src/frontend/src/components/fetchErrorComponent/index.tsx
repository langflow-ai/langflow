import { fetchErrorComponentType } from "../../types/components";
import IconComponent from "../genericIconComponent";

export default function FetchErrorComponent({
  message,
  description,
}: fetchErrorComponentType) {
  return (
    <div role="status" className="m-auto flex flex-col items-center">
      <IconComponent className={`h-16 w-16`} name="Unplug"></IconComponent>
      <br></br>
      <span className="text-lg text-almost-medium-blue">{message}</span>
      <span className="text-lg text-almost-medium-blue">{description}</span>
    </div>
  );
}
