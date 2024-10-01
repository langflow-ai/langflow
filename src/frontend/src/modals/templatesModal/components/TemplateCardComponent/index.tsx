import ForwardedIconComponent from "@/components/genericIconComponent";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { useFolderStore } from "@/stores/foldersStore";
import { FlowType } from "@/types/flow";
import { updateIds } from "@/utils/reactflowUtils";
import { useParams } from "react-router-dom";

interface CardData {
  bgImage: string;
  spiralImage: string;
  icon: string;
  category: string;
  title: string;
  description: string;
  flow: FlowType | undefined;
}

export default function TemplateCard({
  bgImage,
  spiralImage,
  icon,
  category,
  title,
  description,
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
      console.error(`Flow template "${title}" not found`);
    }
  };

  return (
    <div
      className="group relative flex h-full cursor-pointer flex-col overflow-hidden rounded-3xl border"
      onClick={handleClick}
    >
      <img
        src={bgImage}
        alt={`${title} Background`}
        className="absolute inset-2 h-[calc(100%-16px)] w-[calc(100%-16px)] rounded-2xl object-cover"
      />
      <div className="absolute inset-2 h-[calc(100%-16px)] w-[calc(100%-16px)] overflow-hidden rounded-2xl">
        <img
          src={spiralImage}
          alt={`${title} Spiral`}
          className="h-full w-full object-cover opacity-25 transition-all duration-300 group-hover:scale-[102%] group-hover:opacity-60"
        />
      </div>
      <div className="card-shine-effect absolute inset-2 flex h-[calc(100%-16px)] w-[calc(100%-16px)] flex-col items-start gap-4 rounded-2xl p-4 py-6 text-white">
        <div className="flex items-center gap-2 text-white">
          <ForwardedIconComponent name={icon} className="h-4 w-4" />
          <span className="font-mono text-xs font-semibold uppercase tracking-wider">
            {category}
          </span>
        </div>
        <h3 className="text-xl font-bold">{title}</h3>
        <p className="text-xs font-medium opacity-90">{description}</p>
      </div>
    </div>
  );
}
