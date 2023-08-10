import { useContext, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CardComponent } from "../../components/cardComponent";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import { USER_PROJECTS_HEADER } from "../../constants/constants";
import { TabsContext } from "../../contexts/tabsContext";
export default function HomePage() {
  const { flows, setTabId, downloadFlows, uploadFlows, addFlow, removeFlow } =
    useContext(TabsContext);

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
          <Button
            variant="primary"
            onClick={() => {
              addFlow(null, true).then((id) => {
                navigate("/flow/" + id);
              });
            }}
            onMouseOver={() => {
              console.log("Mouse over the button");
            }}
            dropdownContent={
              <div className="dropdown-content">
                
              <Button
                variant="primary"
                onClick={() => {
                  addFlow(null, true).then((id) => {
                    navigate("/flow/" + id);
                  });
                }}>Diagram Editor</Button>
                
              <Button
                variant="primary"
                onClick={() => {
                  addFlow(null, true, true).then((id) => {
                    navigate("/form/" + id);
                  });
                }}>Form</Button>

              </div>
            }
          >
            <IconComponent name="Plus" className="main-page-nav-button" />
            New Project
          </Button>
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
