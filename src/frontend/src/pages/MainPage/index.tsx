import { useContext, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import DropdownButton from "../../components/DropdownButtonComponent";
import { CardComponent } from "../../components/cardComponent";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import { SkeletonCardComponent } from "../../components/skeletonCardComponent";
import { Button } from "../../components/ui/button";
import { USER_PROJECTS_HEADER } from "../../constants/constants";
import { alertContext } from "../../contexts/alertContext";
import { FlowsContext } from "../../contexts/flowsContext";
export default function HomePage(): JSX.Element {
  const {
    flows,
    setTabId,
    downloadFlows,
    uploadFlows,
    addFlow,
    removeFlow,
    uploadFlow,
    isLoading,
  } = useContext(FlowsContext);
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

  // Personal flows display
  return (
    <>
      <Header />
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
            <DropdownButton
              firstButtonName="New Project"
              onFirstBtnClick={() => {
                addFlow(true).then((id) => {
                  navigate("/flow/" + id);
                });
              }}
              options={dropdownOptions}
            />
          </div>
        </div>
        <span className="main-page-description-text">
          Manage your personal projects. Download or upload your collection.
        </span>
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
              <IconComponent
                name="ArrowUpToLine"
                className="h-12 w-12 stroke-1"
              />
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
                flows.map((flow, idx) => (
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
      </div>
    </>
  );
}
