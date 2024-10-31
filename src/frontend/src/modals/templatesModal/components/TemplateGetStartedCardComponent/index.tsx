import ForwardedIconComponent from "@/components/genericIconComponent";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { useFolderStore } from "@/stores/foldersStore";
import { updateIds } from "@/utils/reactflowUtils";
import { BG_NOISE } from "@/utils/styleUtils";
import { cn } from "@/utils/utils";
import { useParams } from "react-router-dom";
import { CardData } from "../../../../types/templates/types";

export default function TemplateGetStartedCardComponent({
  bg,
  spiralImage,
  icon,
  category,
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
      className="group relative flex h-full w-full cursor-pointer flex-col overflow-hidden rounded-3xl border focus-visible:border-ring"
      tabIndex={1}
      onKeyDown={handleKeyDown}
      onClick={handleClick}
    >
      <div
        className={cn(
          "absolute inset-2 h-[calc(100%-16px)] w-[calc(100%-16px)] rounded-2xl object-cover brightness-90 saturate-[140%]",
        )}
        style={{
          backgroundImage: BG_NOISE + "," + bg,
        }}
      />
      <div className="absolute inset-2 h-[calc(100%-16px)] w-[calc(100%-16px)] overflow-hidden rounded-2xl">
        <img
          src={spiralImage}
          alt={`${flow.name} Spiral`}
          className="h-full w-full object-cover opacity-25 transition-all duration-300 group-hover:scale-[102%] group-hover:opacity-60 group-focus-visible:scale-[102%] group-focus-visible:opacity-60"
        />
      </div>
      <div className="card-shine-effect absolute inset-2 flex h-[calc(100%-16px)] min-w-[calc(100%-16px)] flex-col items-start gap-1 rounded-2xl p-4 text-white md:gap-3 lg:gap-4 lg:py-6">
        <div className="flex items-center gap-2 text-white mix-blend-overlay">
          <ForwardedIconComponent name={icon} className="h-4 w-4" />
          <span className="font-mono text-xs font-semibold uppercase tracking-wider">
            {category}
          </span>
        </div>
        <div className="flex w-full items-center justify-between">
          <h3 className="line-clamp-3 text-lg font-bold lg:text-xl">
            {flow.name}
          </h3>
          <ForwardedIconComponent
            name="ArrowRight"
            className="mr-3 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-3 group-hover:opacity-100 group-focus-visible:translate-x-3 group-focus-visible:opacity-100"
          />
        </div>

        <p className="line-clamp-3 w-full overflow-hidden text-sm font-medium opacity-90">
          {flow.description}
        </p>
      </div>
    </div>
  ) : (
    <></>
  );
}
