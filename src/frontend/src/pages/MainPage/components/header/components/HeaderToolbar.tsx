import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useHeaderSearch } from "../hooks/useHeaderSearch";
import { FlowType, ViewType } from "../types";
import BulkActions from "./BulkActions";
import ViewToggle from "./ViewToggle";

interface HeaderToolbarProps {
  flowType: FlowType;
  view: ViewType;
  setView: (view: ViewType) => void;
  setSearch: (search: string) => void;
  setNewProjectModal: (open: boolean) => void;
  selectedFlows: string[];
  onDownload: () => void;
  onDelete: () => void;
  isDownloading: boolean;
  isDeleting: boolean;
}

const HeaderToolbar = ({
  flowType,
  view,
  setView,
  setSearch,
  setNewProjectModal,
  selectedFlows,
  onDownload,
  onDelete,
  isDownloading,
  isDeleting,
}: HeaderToolbarProps) => {
  const { inputValue, handleSearch } = useHeaderSearch(setSearch);

  return (
    <div className="flex justify-between pt-5 px-5 bg-secondary ">
      <div className="flex w-full xl:w-5/12 ">
        <Input
          icon="Search"
          data-testid="search-store-input"
          type="text"
          placeholder={`Search ${flowType}...`}
          className="mr-2 !text-mmd"
          inputClassName="!text-mmd bg-secondary"
          value={inputValue}
          onChange={handleSearch}
        />
        <ViewToggle view={view} setView={setView} />
      </div>
      <div className="flex items-center">
        <BulkActions
          selectedFlows={selectedFlows}
          onDownload={onDownload}
          onDelete={onDelete}
          isDownloading={isDownloading}
          isDeleting={isDeleting}
        />
        <ShadTooltip content="New Flow" side="bottom">
          <Button
            className="flex items-center gap-2 font-semibold"
            onClick={() => setNewProjectModal(true)}
            id="new-project-btn"
            data-testid="new-project-btn"
          >
            <ForwardedIconComponent name="Plus" />
            New Flow
          </Button>
        </ShadTooltip>
      </div>
    </div>
  );
};

export default HeaderToolbar;
