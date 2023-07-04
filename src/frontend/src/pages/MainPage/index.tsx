import { useContext, useEffect } from "react";
import { Download, Upload, Plus, Home, ExternalLink } from "lucide-react";
import { TabsContext } from "../../contexts/tabsContext";
import { Button } from "../../components/ui/button";
import { Link, useNavigate } from "react-router-dom";
import { CardComponent } from "../../components/cardComponent";
import { USER_PROJECTS_HEADER } from "../../constants";
export default function HomePage() {
  const { flows, setTabId, downloadFlows, uploadFlows, addFlow, removeFlow } =
    useContext(TabsContext);
  useEffect(() => {
    setTabId("");
  }, []);
  const navigate = useNavigate();
  return (
    <div className="flex h-full w-full flex-col overflow-auto bg-muted px-16">
      <div className="flex w-full justify-between px-6 py-12 pb-2">
        <span className="flex items-center justify-center gap-2 text-2xl font-semibold">
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
            <Download className="mr-2 w-4" />
            Download Collection
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              uploadFlows();
            }}
          >
            <Upload className="mr-2 w-4" />
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
            <Plus className="mr-2 w-4" />
            New Project
          </Button>
        </div>
      </div>
      <span className="flex w-[60%] px-6 pb-14 text-muted-foreground">
        Manage your personal projects. Download or upload your collection.
      </span>
      <div className="grid w-full gap-4 p-4 md:grid-cols-2 lg:grid-cols-4">
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
                  <ExternalLink className="mr-2 w-4" />
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
