import { useContext, useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import { alertContext } from "../../contexts/alertContext";
import { FlowsContext } from "../../contexts/flowsContext";

import { useNavigate } from "react-router-dom";
import { CardComponent } from "../../components/cardComponent";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import { SkeletonCardComponent } from "../../components/skeletonCardComponent";
import { getExamples } from "../../controllers/API";
import { FlowType } from "../../types/flow";
export default function CommunityPage(): JSX.Element {
  const { flows, setTabId, downloadFlows, uploadFlows, addFlow } =
    useContext(FlowsContext);

  // set null id
  useEffect(() => {
    setTabId("");
  }, []);
  const { setErrorData } = useContext(alertContext);
  const [loadingExamples, setLoadingExamples] = useState(false);
  const [examples, setExamples] = useState<FlowType[]>([]);

  // Show community examples on screen
  function handleExamples(): void {
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

  // Show community examples on page start
  useEffect(() => {
    handleExamples();
  }, []);
  return (
    <>
      <Header />

      <div className="community-page-arrangement">
        <div className="community-page-nav-arrangement">
          <span className="community-page-nav-title">
            <IconComponent name="Users2" className="w-6" />
            Community Examples
          </span>
          <div className="community-page-nav-button">
            <a
              href="https://github.com/logspace-ai/langflow_examples"
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="primary">
                <IconComponent
                  name="GithubIcon"
                  className="main-page-nav-button"
                />
                Add Your Example
              </Button>
            </a>
          </div>
        </div>
        <span className="community-page-description-text">
          Discover and learn from shared examples by the Langflow community. We
          welcome new example contributions that can help our community explore
          new and powerful features.
        </span>
        <div className="community-pages-flows-panel">
          {loadingExamples ? (
            <>
              <SkeletonCardComponent />
              <SkeletonCardComponent />
              <SkeletonCardComponent />
              <SkeletonCardComponent />
            </>
          ) : (
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
                      addFlow(true, flow).then((id) => {
                        navigate("/flow/" + id);
                      });
                    }}
                  >
                    <IconComponent
                      name="GitFork"
                      className="main-page-nav-button"
                    />
                    Fork Example
                  </Button>
                }
              />
            ))
          )}
        </div>
      </div>
    </>
  );
}
