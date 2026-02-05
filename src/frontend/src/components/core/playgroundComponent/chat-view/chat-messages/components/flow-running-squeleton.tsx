import { TextShimmer } from "@/components/ui/TextShimmer";
import LogoIcon from "./bot-message-logo";

export default function FlowRunningSqueleton() {
  return (
    <div className="flex w-full gap-4 rounded-md p-2">
      <LogoIcon />
      <div className="flex items-center">
        <div>
          <TextShimmer className="" duration={1}>
            Flow running...
          </TextShimmer>
        </div>
      </div>
    </div>
  );
}
