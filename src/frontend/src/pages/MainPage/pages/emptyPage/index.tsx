import KendraLabsLogo from "@/assets/kendraLabsLogo200x200.png";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ENABLE_NEW_LOGO } from "@/customization/feature-flags";
import { useFolderStore } from "@/stores/foldersStore";

type EmptyPageProps = {
  setOpenModal: (open: boolean) => void;
};

export const EmptyPage = ({ setOpenModal }: EmptyPageProps) => {
  const folders = useFolderStore((state) => state.folders);

  return (
    <div className="m-0 h-full w-full bg-secondary p-0">
      <div className="text-container">
        <div className="relative z-20 flex w-full flex-col items-center justify-center gap-2">
          {ENABLE_NEW_LOGO ? (
            <img src={KendraLabsLogo} className="h-7 w-8" />
          ) : (
            <span className="fill-foreground text-4xl">⛓️</span>
          )}
          <h3
            className="pt-5 font-chivo text-2xl font-semibold text-foreground"
            data-testid="mainpage_title"
          >
            {folders?.length > 1 ? "Empty folder" : "Start building"}
          </h3>
          <p className="pb-5 text-sm text-secondary-foreground">
            Begin with a template, or start from scratch.
          </p>
          <Button
            variant="default"
            onClick={() => setOpenModal(true)}
            id="new-project-btn"
          >
            <ForwardedIconComponent
              name="Plus"
              aria-hidden="true"
              className="h-4 w-4"
            />
            <span className="hidden whitespace-nowrap font-semibold md:inline">
              New Flow
            </span>
          </Button>
        </div>
      </div>
    </div>
  );
};

export default EmptyPage;
