import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { useFolderStore } from "@/stores/foldersStore";
import { updateIds } from "@/utils/reactflowUtils";
import type { CardData } from "../../../../types/templates/types";

export default function TemplateGetStartedCardComponent({
  icon,
  flow,
}: CardData) {
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const folderIdUrl = folderId ?? myCollectionId;

  const handleClick = () => {
    if (flow) {
      updateIds(flow.data!);
      addFlow({ flow }).then((id) => {
        navigate(`/flow/${id}/folder/${folderIdUrl}`);
      });
      track("New Flow Created", { template: `${flow.name} Template` });
    } else {
      console.error(`Flow template not found`);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleClick();
    }
  };

  return flow ? (
    <div
      className="group relative flex h-full min-h-[200px] bg-[linear-gradient(180deg,#EFA1F0_1.44%,#7421E3_100%)] w-full cursor-pointer flex-col overflow-hidden rounded-lg border focus-visible:border-ring md:min-h-[250px]"
      tabIndex={1}
      onKeyDown={handleKeyDown}
      onClick={handleClick}
    >
      <div className="card-shine-effect absolute flex h-full min-w-full flex-col items-start gap-1 rounded-2xl p-4 text-white">
        <div>
          <div className="h-[32px] w-[32px] rounded-md bg-white/20 flex items-center justify-center mb-4">
            <ForwardedIconComponent name={icon} className="h-4 w-4" />
            {/* <span className="text-xs font-medium uppercase">{category}</span> */}
          </div>
          <div className="flex w-full items-center justify-between">
            <h3 className="line-clamp-3 text-lg text-white font-medium">
              {flow.name}
            </h3>
          </div>
          <p className="line-clamp-3 w-full overflow-hidden text-sm mt-3">
            {flow.description}
          </p>
        </div>
        <div className="flex items-center mt-auto">
          <span className="text-[#FFCC95] text-sm">Getting started</span>
          <ForwardedIconComponent
            name="ChevronRight"
            className="text-[#FFCC95] h-5 w-5 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-1 group-hover:opacity-100 group-focus-visible:translate-x-2 group-focus-visible:opacity-100"
          />
        </div>
      </div>
    </div>
  ) : (
    <></>
  );
}
