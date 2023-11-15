import { cloneDeep } from "lodash";
import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { ReactFlowJsonObject } from "reactflow";
import ShadTooltip from "../../../../components/ShadTooltipComponent";
import IconComponent from "../../../../components/genericIconComponent";
import { TagsSelector } from "../../../../components/tagsSelectorComponent";
import ToggleShadComponent from "../../../../components/toggleShadComponent";
import { Input } from "../../../../components/ui/input";
import { Separator } from "../../../../components/ui/separator";
import { alertContext } from "../../../../contexts/alertContext";
import { FlowsContext } from "../../../../contexts/flowsContext";
import { typesContext } from "../../../../contexts/typesContext";
import { getStoreTags, saveFlowStore } from "../../../../controllers/API";
import ApiModal from "../../../../modals/ApiModal";
import ConfirmationModal from "../../../../modals/ConfirmationModal";
import ExportModal from "../../../../modals/exportModal";
import { APIClassType, APIObjectType } from "../../../../types/api";
import { FlowType } from "../../../../types/flow";
import { getTagsIds } from "../../../../utils/storeUtils";
import {
  nodeColors,
  nodeIconsLucide,
  nodeNames,
} from "../../../../utils/styleUtils";
import {
  classNames,
  removeCountFromString,
  sensitiveSort,
} from "../../../../utils/utils";
import DisclosureComponent from "../DisclosureComponent";
import SidebarDraggableComponent from "./sideBarDraggableComponent";

export default function ExtraSidebar(): JSX.Element {
  const { data, templates, getFilterEdge, setFilterEdge } =
    useContext(typesContext);
  const { flows, tabId, uploadFlow, tabsState, saveFlow, isBuilt } =
    useContext(FlowsContext);
  const { setSuccessData, setErrorData } = useContext(alertContext);
  const [dataFilter, setFilterData] = useState(data);
  const [search, setSearch] = useState("");
  const [sharePublic, setSharePublic] = useState(true);
  const isPending = tabsState[tabId]?.isPending;
  function onDragStart(
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType }
  ): void {
    //start drag event
    var crt = event.currentTarget.cloneNode(true);
    crt.style.position = "absolute";
    crt.style.top = "-500px";
    crt.style.right = "-500px";
    crt.classList.add("cursor-grabbing");
    document.body.appendChild(crt);
    event.dataTransfer.setDragImage(crt, 0, 0);
    event.dataTransfer.setData("nodedata", JSON.stringify(data));
  }

  const [tags, setTags] = useState<string[]>([]);
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());
  const tagListId = useRef<{ id: string; name: string }[]>([]);

  useEffect(() => {
    getStoreTags().then((res) => {
      tagListId.current = res;
      let tags = res.map((tag) => tag.name);
      setTags(tags);
    });
  }, []);

  function handleTagSelection(tag: string) {
    setSelectedTags((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(tag)) {
        newSet.delete(tag);
      } else {
        newSet.add(tag);
      }
      return newSet;
    });
  }

  // Handle showing components after use search input
  function handleSearchInput(e: string) {
    if (e === "") {
      setFilterData(data);
      return;
    }
    setFilterData((_) => {
      let ret = {};
      Object.keys(data).forEach((d: keyof APIObjectType, i) => {
        ret[d] = {};
        let keys = Object.keys(data[d]).filter(
          (nd) =>
            nd.toLowerCase().includes(e.toLowerCase()) ||
            data[d][nd].display_name?.toLowerCase().includes(e.toLowerCase())
        );
        keys.forEach((element) => {
          ret[d][element] = data[d][element];
        });
      });
      return ret;
    });
  }
  const flow = flows.find((flow) => flow.id === tabId);
  useEffect(() => {
    // show components with error on load
    let errors: string[] = [];
    Object.keys(templates).forEach((component) => {
      if (templates[component].error) {
        errors.push(component);
      }
    });
    if (errors.length > 0)
      setErrorData({ title: " Components with errors: ", list: errors });
  }, []);

  function handleBlur() {
    // check if search is search to reset fitler on click input
    if ((!search && search === "") || search === "search") {
      setFilterData(data);
      setFilterEdge([]);
      setSearch("");
    }
  }

  useEffect(() => {
    if (getFilterEdge.length === 0 && search === "") {
      setFilterData(data);
      setFilterEdge([]);
      setSearch("");
    }
  }, [getFilterEdge]);

  useEffect(() => {
    handleSearchInput(search);
  }, [data]);

  const handleShareFlow = () => {
    const reactFlow = flow!.data as ReactFlowJsonObject;
    const saveFlow: FlowType = {
      name: flow!.name,
      id: flow!.id,
      description: flow!.description,
      data: {
        ...reactFlow,
      },
      is_component: false,
    };
    saveFlowStore(
      saveFlow,
      getTagsIds(Array.from(selectedTags), tagListId),
      sharePublic
    ).then(
      () => {
        setSuccessData({
          title: "Flow shared successfully",
        });
      },
      (err) => {
        setErrorData({
          title: "Error sharing flow",
          list: [err["response"]["data"]["detail"]],
        });
      }
    );
  };

  useEffect(() => {
    if (getFilterEdge?.length > 0) {
      setFilterData((_) => {
        let dataClone = cloneDeep(data);
        let ret = {};
        Object.keys(dataClone).forEach((d: keyof APIObjectType, i) => {
          ret[d] = {};
          if (getFilterEdge.some((x) => x.family === d)) {
            ret[d] = dataClone[d];

            const filtered = getFilterEdge
              .filter((x) => x.family === d)
              .pop()
              .type.split(",");

            for (let i = 0; i < filtered.length; i++) {
              filtered[i] = filtered[i].trimStart();
            }

            if (filtered.some((x) => x !== "")) {
              let keys = Object.keys(dataClone[d]).filter((nd) =>
                filtered.includes(nd)
              );
              Object.keys(dataClone[d]).forEach((element) => {
                if (!keys.includes(element)) {
                  delete ret[d][element];
                }
              });
            }
          }
        });
        setSearch("");
        return ret;
      });
    }
  }, [getFilterEdge, data]);

  const ModalMemo = useMemo(
    () => (
      <ConfirmationModal
        index={0}
        modalContentTitle="Are you sure you want to share this flow?"
        title="Share Flow"
        confirmationText="Share"
        icon="Share2"
        size="small-h-full"
        onConfirm={() => {
          handleShareFlow();
        }}
        titleHeader=""
        cancelText="Cancel"
      >
        <ConfirmationModal.Content>
          <div className="flex h-full w-full flex-col gap-3">
            <div className="flex justify-start pt-4 align-middle">
              <ToggleShadComponent
                disabled={false}
                size="medium"
                setEnabled={setSharePublic}
                enabled={sharePublic}
              />
              <div
                className="cursor-pointer pl-1"
                onClick={() => {
                  setSharePublic(!sharePublic);
                }}
              >
                {sharePublic ? (
                  <span>
                    This flow will be avaliable <b>for everyone</b>
                  </span>
                ) : (
                  <span>
                    This flow will be avaliable <b>just for you</b>
                  </span>
                )}
              </div>
            </div>
            <div className="w-full pt-2">
              <span className="text-sm">Add some tags to your Flow</span>
              <TagsSelector
                tags={tags}
                selectedTags={selectedTags}
                setSelectedTags={handleTagSelection}
              />
            </div>
          </div>
        </ConfirmationModal.Content>
        <ConfirmationModal.Trigger tolltipContent="Share" side="top">
          <div className={classNames("extra-side-bar-buttons")}>
            <IconComponent name="Share2" className="side-bar-button-size" />
          </div>
        </ConfirmationModal.Trigger>
      </ConfirmationModal>
    ),
    [sharePublic, tags, selectedTags]
  );

  const ExportMemo = useMemo(
    () => (
      <ExportModal>
        <ShadTooltip content="Export" side="top">
          <div className={classNames("extra-side-bar-buttons")}>
            <IconComponent name="FileDown" className="side-bar-button-size" />
          </div>
        </ShadTooltip>
      </ExportModal>
    ),
    []
  );

  return (
    <div className="side-bar-arrangement">
      <div className="side-bar-buttons-arrangement">
        <div className="side-bar-button">
          <ShadTooltip content="Import" side="top">
            <button
              className="extra-side-bar-buttons"
              onClick={() => {
                uploadFlow(false);
              }}
            >
              <IconComponent name="FileUp" className="side-bar-button-size " />
            </button>
          </ShadTooltip>
        </div>
        <div className="side-bar-button">{ExportMemo}</div>
        <ShadTooltip content={"Code"} side="top">
          <div className="side-bar-button">
            {flow && flow.data && (
              <ApiModal flow={flow}>
                <button
                  className={"w-full " + (!isBuilt ? "button-disable" : "")}
                >
                  <div className={classNames("extra-side-bar-buttons")}>
                    <IconComponent
                      name="Code2"
                      className={
                        "side-bar-button-size" +
                        (isBuilt ? " " : " extra-side-bar-save-disable")
                      }
                    />
                  </div>
                </button>
              </ApiModal>
            )}
          </div>
        </ShadTooltip>
        <div className="side-bar-button">
          <ShadTooltip content="Save" side="top">
            <div>
              <button
                className={
                  "extra-side-bar-buttons " +
                  (isPending ? "" : "button-disable")
                }
                onClick={(event) => {
                  saveFlow(flow!);
                }}
              >
                <IconComponent
                  name="Save"
                  className={
                    "side-bar-button-size" +
                    (isPending ? " " : " extra-side-bar-save-disable")
                  }
                />
              </button>
            </div>
          </ShadTooltip>
        </div>

        <div className="side-bar-button">{ModalMemo}</div>
      </div>
      <Separator />
      <div className="side-bar-search-div-placement">
        <Input
          onFocusCapture={() => handleBlur()}
          type="text"
          name="search"
          id="search"
          placeholder="Search"
          className="nopan nodelete nodrag noundo nocopy input-search"
          onChange={(event) => {
            handleSearchInput(event.target.value);
            // Set search input state
            setSearch(event.target.value);
          }}
        />
        <div className="search-icon">
          <IconComponent
            name="Search"
            className={"h-5 w-5 stroke-[1.5] text-primary"}
            aria-hidden="true"
          />
        </div>
      </div>

      <div className="side-bar-components-div-arrangement">
        {Object.keys(dataFilter)
          .sort()
          .map((SBSectionName: keyof APIObjectType, index) =>
            Object.keys(dataFilter[SBSectionName]).length > 0 ? (
              <DisclosureComponent
                openDisc={
                  getFilterEdge.length !== 0 || search.length !== 0
                    ? true
                    : false
                }
                key={index + search + JSON.stringify(getFilterEdge)}
                button={{
                  title: nodeNames[SBSectionName] ?? nodeNames.unknown,
                  Icon:
                    nodeIconsLucide[SBSectionName] ?? nodeIconsLucide.unknown,
                }}
              >
                <div className="side-bar-components-gap">
                  {Object.keys(dataFilter[SBSectionName])
                    .sort((a, b) =>
                      sensitiveSort(
                        dataFilter[SBSectionName][a].display_name,
                        dataFilter[SBSectionName][b].display_name
                      )
                    )
                    .map((SBItemName: string, index) => (
                      <ShadTooltip
                        content={
                          dataFilter[SBSectionName][SBItemName].display_name
                        }
                        side="right"
                        key={index}
                      >
                        <SidebarDraggableComponent
                          sectionName={SBSectionName as string}
                          apiClass={dataFilter[SBSectionName][SBItemName]}
                          key={SBItemName}
                          onDragStart={(event) =>
                            onDragStart(event, {
                              //split type to remove type in nodes saved with same name removing it's
                              type: removeCountFromString(SBItemName),
                              node: dataFilter[SBSectionName][SBItemName],
                            })
                          }
                          color={nodeColors[SBSectionName]}
                          itemName={SBItemName}
                          //convert error to boolean
                          error={!!dataFilter[SBSectionName][SBItemName].error}
                          display_name={
                            dataFilter[SBSectionName][SBItemName].display_name
                          }
                          official={
                            dataFilter[SBSectionName][SBItemName].official ===
                            false
                              ? false
                              : true
                          }
                        />
                      </ShadTooltip>
                    ))}
                </div>
              </DisclosureComponent>
            ) : (
              <div key={index}></div>
            )
          )}
      </div>
    </div>
  );
}
