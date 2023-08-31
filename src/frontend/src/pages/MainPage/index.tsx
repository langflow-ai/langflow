import { useContext, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CardComponent } from "../../components/cardComponent";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import { SkeletonCardComponent } from "../../components/skeletonCardComponent";
import { Button } from "../../components/ui/button";
import { USER_PROJECTS_HEADER } from "../../constants/constants";
import { TabsContext } from "../../contexts/tabsContext";
import DropdownButton from "../../components/DropdownButtonComponent";
export default function HomePage(): JSX.Element {
  const {
    flows,
    setTabId,
    downloadFlows,
    uploadFlows,
    addFlow,
    removeFlow, uploadFlow,
    isLoading,
  } = useContext(TabsContext);
  const dropdownOptions = [{name: "Import from JSON", onBtnClick: () => uploadFlow(true).then((id) => {
    navigate("/flow/" + id);
  })}]

  // Set a null id
  useEffect(() => {
    setTabId("");
  }, []);
  const navigate = useNavigate();

  useEffect(() => {
    console.log(isLoading);
  }, [isLoading]);

  // Personal flows display
  return (
    <>
      <Header />
      <div className="main-page-panel">
        <div className="main-page-nav-arrangement">
          <span className="main-page-nav-title">
            <IconComponent name="Home" className="w-6" />
            {USER_PROJECTS_HEADER}
          </span>
          <div className="button-div-style">
            <Button
              variant="primary"
              onClick={() => {
                downloadFlows();
              }}
            >
              <IconComponent name="Download" className="main-page-nav-button" />
              Download Collection
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                uploadFlows();
              }}
            >
              <IconComponent name="Upload" className="main-page-nav-button" />
              Upload Collection
            </Button>
            <DropdownButton
              firstButtonName="New Project"
              onFirstBtnClick={() => {
                addFlow(null!, true).then((id) => {
                  navigate("/flow/" + id);
                });
              }}
              options={dropdownOptions}
            />
          </div>
        </div>
        <span className="main-page-description-text">
          Manage your personal projects. Download or upload your collection. 
        </span>
        <div className="main-page-flows-display">
          {isLoading && flows.length == 0 ? (
            <>
              <SkeletonCardComponent />
              <SkeletonCardComponent />
              <SkeletonCardComponent />
              <SkeletonCardComponent />
            </>
          ) : (
            flows.map((flow, idx) => (
              <CardComponent
                key={idx}
                flow={flow}
                id={flow.id}
                button={
                  <Link to={"/flow/" + flow.id}>
                    <Button
                      variant="outline"
                      size="sm"
                      className="whitespace-nowrap "
                    >
                      <IconComponent
                        name="ExternalLink"
                        className="main-page-nav-button"
                      />
                      Edit Flow
                    </Button>
                  </Link>
                }
                onDelete={() => {
                  removeFlow(flow.id);
                }}
              />
            ))
          )}
        </div>
      </div>
    </>
  );
}
