import { useContext, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CardComponent } from "../../components/cardComponent";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { USER_PROJECTS_HEADER } from "../../constants/constants";
import { TabsContext } from "../../contexts/tabsContext";
import NewProjectModal from "../../modals/NewProjectModal";
import ShadTooltip from "../../components/ShadTooltipComponent";
import { classNames } from "../../utils/utils";

export default function HomePage() {
  const { flows, setTabId, downloadFlows, uploadFlows, addFlow, removeFlow } =
    useContext(TabsContext);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Set a null id
  useEffect(() => {
    setTabId("");
  }, []);
  const navigate = useNavigate();

  // Personal flows display
  return (
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
          <NewProjectModal >
            <ShadTooltip content="New Project" side="top">
                <div className={classNames("extra-side-bar-buttons")}>
                    <IconComponent name="Plus" className="side-bar-button-size" /> New Project
                </div>
            </ShadTooltip>
        </NewProjectModal>
        </div>
      </div>

        

      <span className="main-page-description-text">
        Manage your personal projects. Download or upload your collection.
      </span>
      <div className="main-page-flows-display">
        {flows.map((flow, idx) => (
          <CardComponent
            key={idx}
            flow={flow}
            id={flow.id}
            button={
              <div className="button-container">
                
              {(
                <Link to={"/form/" + flow.id}>
                  <Button
                    variant="outline"
                    size="sm"
                    className="whitespace-nowrap "
                  >
                    <IconComponent
                      name="ExternalLink"
                      className="main-page-nav-button"
                    />
                    Edit Form
                  </Button>
                </Link>
              )}
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
              </div>
            }
            onDelete={() => {
              removeFlow(flow.id);
            }}
          />
        ))}
      </div>
    </div>
  );
}
