import { useContext, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { darkContext } from "../../contexts/darkContext";
import { TabsContext } from "../../contexts/tabsContext";
import { getVersion } from "../../controllers/API";
import Page from "../FlowPage/components/PageComponent";

export default function ViewPage() {
  const { flows, tabId, setTabId } = useContext(TabsContext);
  const { setDark } = useContext(darkContext);
  const { id, theme } = useParams();

  // Set flow tab id
  useEffect(() => {
    setTabId(id!);
  }, [id]);

  useEffect(() => {
    if (theme) {
      setDark(theme === "dark");
    } else {
      setDark(false);
    }
  }, [theme]);

  // Initialize state variable for the version
  const [version, setVersion] = useState("");
  useEffect(() => {
    getVersion().then((data) => {
      setVersion(data.version);
    });
  }, []);

  return (
    <div className="flow-page-positioning">
      {flows.length > 0 &&
        tabId !== "" &&
        flows.findIndex((flow) => flow.id === tabId) !== -1 && (
          <Page view flow={flows.find((flow) => flow.id === tabId)!} />
        )}
    </div>
  );
}
