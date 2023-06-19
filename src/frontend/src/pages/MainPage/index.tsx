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
    <div className="w-full h-full flex overflow-auto flex-col bg-muted px-16">
      <div className="w-full flex justify-between py-12 pb-2 px-6">
        <span className="text-2xl flex items-center justify-center gap-2 font-semibold">
          <Home className="w-6" />
          {USER_PROJECTS_HEADER}
        </span>
        <div className="flex gap-2">
          <Button
            variant="primary"
            onClick={() => {
              downloadFlows();
            }}
          >
            <Download className="w-4 mr-2" />
            Download Collection
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              uploadFlows();
            }}
          >
            <Upload className="w-4 mr-2" />
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
            <Plus className="w-4 mr-2" />
            New Project
          </Button>
        </div>
      </div>
      <span className="flex pb-14 px-6 text-muted-foreground w-[60%]">
        Manage your personal projects. Download or upload your collection.
      </span>
      <div className="w-full p-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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
                  <ExternalLink className="w-4 mr-2" />
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
