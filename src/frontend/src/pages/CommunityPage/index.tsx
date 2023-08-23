import { useContext, useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import { alertContext } from "../../contexts/alertContext";
import { TabsContext } from "../../contexts/tabsContext";

import Fuse from "fuse.js";
import { useNavigate } from "react-router-dom";
import { CardComponent } from "../../components/cardComponent";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import { Input } from "../../components/ui/input";
import { getExamples } from "../../controllers/API";
import { FlowType } from "../../types/flow";
export default function CommunityPage() {
  const { flows, setTabId, downloadFlows, uploadFlows, addFlow } =
    useContext(TabsContext);

  // set null id
  useEffect(() => {
    setTabId("");
  }, []);
  const { setErrorData } = useContext(alertContext);
  const [loadingExamples, setLoadingExamples] = useState(false);
  const [examples, setExamples] = useState<FlowType[]>([]);

  // Show community examples on screen
  function handleExamples() {
    setLoadingExamples(true);
    getExamples()
      .then((result) => {
        setLoadingExamples(false);
        setExamples(result);
        setSearchData(result);
      })
      .catch((error) =>
        setErrorData({
          title: "there was an error loading examples, please try again",
          list: [error.message],
        })
      );
  }
  const navigate = useNavigate();

  const [searchData, setSearchData] = useState(examples);
  const searchItem = (query) => {
    if (!query) {
      setSearchData(examples);
      return;
    }
    const fuse = new Fuse(examples, {
      keys: ["name", "description"],
    });
    const result = fuse.search(query);
    const finalResult = [];
    if (result.length) {
      result.forEach((item) => {
        finalResult.push(item.item);
      });
      setSearchData(finalResult);
    } else {
      setSearchData([]);
    }
  };

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
        </div>
        <span className="community-page-description-text">
          Discover and learn from shared examples by the Langflow community. We
          welcome new example contributions that can help our community explore
          new and powerful features.
        </span>
        <div className="flex w-full flex-col gap-4 p-4">
          <div className="flex justify-between">
            <div className="flex w-96 items-center gap-4">
              <Input
                placeholder="Search Examples"
                onChange={(e) => searchItem(e.target.value)}
              />
              <IconComponent name="Search" className="w-6 text-foreground" />
            </div>
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
          <div className="community-pages-flows-panel">
            {!loadingExamples &&
              searchData.map((flow, idx) => (
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
                      <IconComponent
                        name="GitFork"
                        className="main-page-nav-button"
                      />
                      Fork Example
                    </Button>
                  }
                />
              ))}
          </div>
        </div>
      </div>
    </>
  );
}
