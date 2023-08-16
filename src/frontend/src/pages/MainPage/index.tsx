import { useContext, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import { Button } from "../../components/ui/button";
import { USER_PROJECTS_HEADER } from "../../constants/constants";
import { TabsContext } from "../../contexts/tabsContext";
export default function HomePage(): JSX.Element {
  const { flows, setTabId, downloadFlows, uploadFlows, addFlow, removeFlow } =
    useContext(TabsContext);

  // Set a null id
  useEffect(() => {
    setTabId("");
  }, []);
  const navigate = useNavigate();

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
            <Button
              variant="primary"
              onClick={() => {
                addFlow(null, true).then((id) => {
                  navigate("/flow/" + id);
                });
              }}
            >
              <IconComponent name="Plus" className="main-page-nav-button" />
              New Project
            </Button>
          </div>
        </div>
        <span className="main-page-description-text">
          Manage your personal projects. Download or upload your collection.
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
          <Button
            variant="primary"
            onClick={() => {
              addFlow(null!, true).then((id) => {
                navigate("/flow/" + id);
              });
            }}
          >
            <IconComponent name="Plus" className="main-page-nav-button" />
            New Project
          </Button>
        </div>
      </div>
    </>
  );
}
