import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useFolderStore } from "../../../../../../stores/foldersStore";

type TabsSearchComponentProps = {
  tabsOptions: string[];
  setActiveTab: (tab: string) => void;
  loading: boolean;
  tabActive: string;
};

const TabsSearchComponent = ({
  tabsOptions,
  setActiveTab,
  loading,
  tabActive,
}: TabsSearchComponentProps) => {
  const navigate = useNavigate();
  const folderUrl = useFolderStore((state) => state.folderUrl);

  const changeLocation = (tabOption) => {
    const location = window.location.pathname;
    let newLocation = "";
    switch (tabOption) {
      case "Flows":
        newLocation = location.replace(/components|all/, "flows");
        break;
      case "Components":
        newLocation = location.replace(/flows|all/, "components");
        break;
      default:
        newLocation = location.replace(/flows|components/, "all");
        break;
    }

    navigate(newLocation, { state: { folderId: folderUrl } });
  };

  useEffect(() => {
    const path = window.location.pathname;
    if (path.includes("components")) {
      setActiveTab("Components");
    } else if (path.includes("flows")) {
      setActiveTab("Flows");
    } else {
      setActiveTab("All");
    }
  }, [window.location.pathname]);

  return (
    <>
      <div className="ml-4 flex w-full gap-2 border-b border-border">
        {tabsOptions.map((tabOption, index) => {
          return (
            <button
              key={index}
              data-testid={`${tabOption}-button-store`}
              disabled={loading}
              onClick={() => {
                changeLocation(tabOption);
              }}
              className={
                (tabActive === tabOption
                  ? "border-b-2 border-primary p-3"
                  : " border-b-2 border-transparent p-3 text-muted-foreground hover:text-primary") +
                (loading ? " cursor-not-allowed " : "")
              }
            >
              {tabOption}
            </button>
          );
        })}
      </div>
    </>
  );
};
export default TabsSearchComponent;
