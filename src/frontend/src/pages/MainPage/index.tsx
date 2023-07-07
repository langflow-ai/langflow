import { Download, ExternalLink, Home, Plus, Upload } from "lucide-react";
import { useContext, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CardComponent } from "../../components/cardComponent";
import { Button } from "../../components/ui/button";
import { USER_PROJECTS_HEADER } from "../../constants";
import { TabsContext } from "../../contexts/tabsContext";
export default function HomePage() {
  const { flows, setTabId, downloadFlows, uploadFlows, addFlow, removeFlow } =
    useContext(TabsContext);
  useEffect(() => {
    setTabId("");
  }, []);
  const navigate = useNavigate();
  return (
    <div className="main-page-panel">
      <div className="main-page-nav-arrangement">
        <span className="main-page-nav-title">
          <Home className="w-6" />
          {USER_PROJECTS_HEADER}
        </span>
        <div className="button-div-style">
          <Button
            variant="primary"
            onClick={() => {
              downloadFlows();
            }}
          >
            <Download className="main-page-nav-button" />
            Download Collection
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              uploadFlows();
            }}
          >
            <Upload className="main-page-nav-button" />
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
            <Plus className="main-page-nav-button" />
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
              <Link to={"/flow/" + flow.id}>
                <Button
                  variant="outline"
                  size="sm"
                  className="whitespace-nowrap "
                >
                  <ExternalLink className="main-page-nav-button" />
                  Edit Flow
                </Button>
              </Link>
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
