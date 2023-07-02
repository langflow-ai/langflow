import { useContext, useEffect, useState } from "react";
import { GithubIcon, Users2, GitFork } from "lucide-react";
import { TabsContext } from "../../contexts/tabsContext";
import { alertContext } from "../../contexts/alertContext";
import { Button } from "../../components/ui/button";

import { getExamples } from "../../controllers/API";
import { FlowType } from "../../types/flow";
import { CardComponent } from "../../components/cardComponent";
import { useNavigate } from "react-router-dom";
export default function CommunityPage() {
  const { flows, setTabId, downloadFlows, uploadFlows, addFlow } =
    useContext(TabsContext);
  useEffect(() => {
    setTabId("");
  }, []);
  const { setErrorData } = useContext(alertContext);
  const [loadingExamples, setLoadingExamples] = useState(false);
  const [examples, setExamples] = useState<FlowType[]>([]);
  function handleExamples() {
    setLoadingExamples(true);
    getExamples()
      .then((result) => {
        setLoadingExamples(false);
        setExamples(result);
      })
      .catch((error) =>
        setErrorData({
          title: "there was an error loading examples, please try again",
          list: [error.message],
        })
      );
  }
  const navigate = useNavigate();

  useEffect(() => {
    handleExamples();
  }, []);
  return (
    <div className="flex h-full w-full flex-col overflow-auto bg-muted px-16">
      <div className="flex w-full justify-between px-6 py-12 pb-2">
        <span className="flex items-center justify-center gap-2 text-2xl font-semibold">
          <Users2 className="w-6" />
          Community Examples
        </span>
        <div className="flex gap-2">
          <a
            href="https://github.com/logspace-ai/langflow_examples"
            target="_blank"
            rel="noreferrer"
          >
            <Button variant="primary">
              <GithubIcon className="mr-2 w-4" />
              Add Your Example
            </Button>
          </a>
        </div>
      </div>
      <span className="flex w-[70%] px-6 pb-8 text-muted-foreground">
        Discover and learn from shared examples by the LangFlow community. We
        welcome new example contributions that can help our community explore
        new and powerful features.
      </span>
      <div className="grid w-full gap-4 p-4 md:grid-cols-2 lg:grid-cols-4">
        {!loadingExamples &&
          examples.map((flow, idx) => (
            <CardComponent
              key={idx}
              flow={flow}
              id={flow.id}
              button={
                <Button
                  variant="outline"
                  size="sm"
                  className="whitespace-nowrap "
                  onClick={() => {
                    addFlow(flow, true).then((id) => {
                      navigate("/flow/" + id);
                    });
                  }}
                >
                  <GitFork className="mr-2 w-4" />
                  Fork Example
                </Button>
              }
            />
          ))}
      </div>
    </div>
  );
}
