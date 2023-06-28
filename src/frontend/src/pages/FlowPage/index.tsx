import { useContext, useEffect, useState } from "react";
import Page from "./components/PageComponent";
import { TabsContext } from "../../contexts/tabsContext";
import { useParams } from "react-router-dom";
import { getVersion } from "../../controllers/API";

export default function FlowPage() {
  const { flows, tabId, setTabId } = useContext(TabsContext);
  const { id } = useParams();
  useEffect(() => {
    setTabId(id);
  }, [id]);

  // Initialize state variable for the version
  const [version, setVersion] = useState("");
  useEffect(() => {
    getVersion().then((data) => {
      setVersion(data.version);
    });
  }, []);

  return (
    <div className="h-full w-full overflow-hidden">
      {flows.length > 0 &&
        tabId !== "" &&
        flows.findIndex((flow) => flow.id === tabId) !== -1 && (
          <Page flow={flows.find((flow) => flow.id === tabId)} />
        )}
      <a
        target={"_blank"}
        href="https://logspace.ai/"
        className="absolute left-7 bottom-2 flex h-6 cursor-pointer flex-col items-center justify-start overflow-hidden rounded-lg bg-foreground px-2 text-center font-sans text-xs tracking-wide text-secondary transition-all duration-500 ease-in-out hover:h-12"
      >
        {version && <div className="mt-1">⛓️ LangFlow v{version}</div>}
        <div className={version ? "mt-2" : "mt-1"}>Created by Logspace</div>
      </a>
    </div>
  );
}
