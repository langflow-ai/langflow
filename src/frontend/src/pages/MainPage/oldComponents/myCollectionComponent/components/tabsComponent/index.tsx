import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useCallback } from "react";

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
  const navigate = useCustomNavigate();

  const changeLocation = useCallback(
    (tabOption: string) => {
      const location = window.location.pathname;
      let newLocation = "";
      switch (tabOption) {
        case "Flows":
          newLocation = location.replace(/.*\/(?:all|components)/, "/flows");
          break;
        case "Components":
          newLocation = location.replace(/.*\/(?:flows|all)/, "/components");
          break;
        default:
          newLocation = location.replace(/.*\/(?:flows|components)/, "/all");
          break;
      }
      navigate(newLocation);
      setActiveTab(tabOption);
    },
    [navigate, setActiveTab],
  );

  return (
    <>
      <div className="ml-4 flex w-full gap-2 border-b border-border">
        {tabsOptions.map((tabOption, index) => (
          <button
            key={index}
            data-testid={`${tabOption}-button-store`}
            disabled={loading}
            onClick={() => changeLocation(tabOption)}
            className={
              (tabActive === tabOption
                ? "border-b-2 border-primary p-3"
                : "border-b-2 border-transparent p-3 text-muted-foreground hover:text-primary") +
              (loading ? " cursor-not-allowed" : "")
            }
          >
            {tabOption}
          </button>
        ))}
      </div>
    </>
  );
};

export default TabsSearchComponent;
