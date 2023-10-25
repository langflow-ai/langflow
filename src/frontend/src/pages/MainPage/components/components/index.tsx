import { useContext, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CardComponent } from "../../../../components/cardComponent";
import IconComponent from "../../../../components/genericIconComponent";
import { SkeletonCardComponent } from "../../../../components/skeletonCardComponent";
import { Button } from "../../../../components/ui/button";
import { alertContext } from "../../../../contexts/alertContext";
import { TabsContext } from "../../../../contexts/tabsContext";

export default function ComponentsComponent() {
  const {
    flows,
    setTabId,
    downloadFlows,
    uploadFlows,
    addFlow,
    removeFlow,
    uploadFlow,
    isLoading,
  } = useContext(TabsContext);
  const { setErrorData } = useContext(alertContext);

  const dropdownOptions = [
    {
      name: "Import from JSON",
      onBtnClick: () =>
        uploadFlow(true).then((id) => {
          navigate("/flow/" + id);
        }),
    },
  ];

  // Set a null id
  useEffect(() => {
    setTabId("");
  }, []);
  const navigate = useNavigate();

  const [isDragging, setIsDragging] = useState(false);

  const dragOver = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setIsDragging(true);
    }
  };

  const dragEnter = (e) => {
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setIsDragging(true);
    }
    e.preventDefault();
  };

  const dragLeave = () => {
    setIsDragging(false);
  };

  const fileDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      if (e.dataTransfer.files.item(0).type === "application/json") {
        uploadFlow(true, e.dataTransfer.files.item(0)!);
      } else {
        setErrorData({
          title: "Invalid file type",
          list: ["Please upload a JSON file"],
        });
      }
    }
  };

  return (
    <div
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={fileDrop}
      className={
        "h-full w-full " +
        (isDragging
          ? "mb-24 flex flex-col items-center justify-center gap-4 text-2xl font-light"
          : "")
      }
    >
      {isDragging ? (
        <>
          <IconComponent name="ArrowUpToLine" className="h-12 w-12 stroke-1" />
          Drop your flow here
        </>
      ) : (
        <div className="main-page-flows-display">
          {isLoading && flows.length == 0 ? (
            <>
              <SkeletonCardComponent />
              <SkeletonCardComponent />
              <SkeletonCardComponent />
              <SkeletonCardComponent />
            </>
          ) : (
            flows
              .filter((flow) => flow.is_component)
              .map((flow, idx) => (
                <CardComponent
                  key={idx}
                  data={flow}
                  id={flow.id}
                  button={
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
                  }
                  onDelete={() => {
                    removeFlow(flow.id);
                  }}
                />
              ))
          )}
        </div>
      )}
    </div>
  );
}
