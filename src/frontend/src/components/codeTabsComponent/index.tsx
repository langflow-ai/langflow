import { cloneDeep } from "lodash";
import { useEffect, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import CodeAreaComponent from "../../components/codeAreaComponent";
import Dropdown from "../../components/dropdownComponent";
import FloatComponent from "../../components/floatComponent";
import InputFileComponent from "../../components/inputFileComponent";
import InputListComponent from "../../components/inputListComponent";
import IntComponent from "../../components/intComponent";
import PromptAreaComponent from "../../components/promptComponent";
import TextAreaComponent from "../../components/textAreaComponent";
import ToggleShadComponent from "../../components/toggleShadComponent";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import { LANGFLOW_SUPPORTED_TYPES } from "../../constants/constants";
import getTabsOrder from "../../modals/apiModal/utils/get-tabs-order";
import { Case } from "../../shared/components/caseComponent";
import { useDarkStore } from "../../stores/darkStore";
import useFlowStore from "../../stores/flowStore";
import { codeTabsPropsType } from "../../types/components";
import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
} from "../../utils/reactflowUtils";
import { classNames, cn } from "../../utils/utils";
import AccordionComponent from "../accordionComponent";
import DictComponent from "../dictComponent";
import IconComponent from "../genericIconComponent";
import InputComponent from "../inputComponent";
import KeypairListComponent from "../keypairListComponent";
import ShadTooltip from "../shadTooltipComponent";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";

export default function CodeTabsComponent({
  flow,
  tabs,
  activeTab,
  setActiveTab,
  isMessage,
  tweaks,
  setActiveTweaks,
  activeTweaks,
  allowExport = false,
  isThereTweaks = false,
  isThereWH = false,
}: codeTabsPropsType) {
  const [isCopied, setIsCopied] = useState<Boolean>(false);
  const [data, setData] = useState(flow ? flow["data"]!["nodes"] : null);
  const dark = useDarkStore((state) => state.dark);
  const unselectAll = useFlowStore((state) => state.unselectAll);
  const [errorDuplicateKey, setErrorDuplicateKey] = useState(false);

  useEffect(() => {
    if (flow && flow["data"]!["nodes"]) {
      setData(flow["data"]!["nodes"]);
    }
  }, [flow]);

  useEffect(() => {
    if (tweaks && data) {
      unselectAll();
    }
  }, []);

  const copyToClipboard = () => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    navigator.clipboard.writeText(tabs[activeTab].code).then(() => {
      setIsCopied(true);

      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    });
  };

  const type = (node, templateParam) => {
    return node.data.node.template[templateParam].type;
  };

  const tabsOrder = getTabsOrder(isThereWH, isThereTweaks);

  return (
    <Tabs
      value={activeTab}
      className={
        "api-modal-tabs inset-0 m-0 " +
        (isMessage ? "dark" : "") +
        (dark && isMessage ? "bg-background" : "")
      }
      onValueChange={(value) => {
        setActiveTab(value);
      }}
    >
      <div className="api-modal-tablist-div">
        {tabs.length > 0 && tabs[0].name !== "" ? (
          <TabsList>
            {tabs.map((tab, index) => (
              <TabsTrigger
                className={
                  isMessage ? "data-[state=active]:bg-primary-foreground" : ""
                }
                key={index}
                value={index.toString()}
              >
                {tab.name}
              </TabsTrigger>
            ))}
          </TabsList>
        ) : (
          <div></div>
        )}

        <div className="float-right mx-2 mb-1 mt-2 flex items-center gap-4">
          {tweaks && (
            <div className={Number(activeTab) > 2 ? "hidden" : "flex gap-2"}>
              <Switch
                style={{
                  transform: `scaleX(${0.7}) scaleY(${0.7})`,
                }}
                id="tweaks-switch"
                onCheckedChange={setActiveTweaks}
                autoFocus={false}
              />
              <Label
                className={cn(
                  "relative right-1 top-[4px] text-xs font-medium text-muted-foreground",
                  activeTweaks ? "text-primary" : "",
                )}
                htmlFor="tweaks-switch"
              >
                Tweaks
              </Label>
            </div>
          )}

          {Number(activeTab) < 5 && (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="text-muted-foreground"
                onClick={copyToClipboard}
              >
                {isCopied ? (
                  <IconComponent name="Check" className="h-4 w-4" />
                ) : (
                  <IconComponent name="Copy" className="h-4 w-4" />
                )}
              </Button>
            </>
          )}
        </div>
      </div>

      {tabs.map((tab, idx) => (
        <TabsContent
          value={idx.toString()}
          className="api-modal-tabs-content overflow-hidden"
          key={idx} // Remember to add a unique key prop
        >
          {tabsOrder[idx].toLowerCase() !== "tweaks" ? (
            <div className="flex h-full w-full flex-col">
              {tab.description && (
                <div
                  className="mb-2 w-full text-left text-sm"
                  dangerouslySetInnerHTML={{ __html: tab.description }}
                ></div>
              )}
              <SyntaxHighlighter
                language={tab.language}
                style={oneDark}
                className="mt-0 h-full overflow-auto rounded-sm text-left custom-scroll"
              >
                {tab.code}
              </SyntaxHighlighter>
            </div>
          ) : tabsOrder[idx].toLowerCase() === "tweaks" ? (
            <>
              <div className="api-modal-according-display">
                <div
                  className={classNames(
                    "h-[70vh] w-full overflow-y-auto overflow-x-hidden rounded-lg bg-muted custom-scroll",
                  )}
                >
                  {data?.map((node: any, i) => (
                    <div className="px-3" key={i}>
                      {tweaks?.tweaksList!.includes(node["data"]["id"]) && (
                        <AccordionComponent
                          trigger={
                            <ShadTooltip
                              side="top"
                              styleClasses="z-50"
                              content={node["data"]["id"]}
                            >
                              <div>{node["data"]["node"]["display_name"]}</div>
                            </ShadTooltip>
                          }
                          keyValue={node["data"]["id"]}
                        >
                          <div className="api-modal-table-arrangement">
                            <Table className="table-fixed bg-muted outline-1">
                              <TableHeader className="h-10 border-input text-xs font-medium text-ring">
                                <TableRow className="">
                                  <TableHead className="h-7 text-center">
                                    PARAM
                                  </TableHead>
                                  <TableHead className="h-7 p-0 text-center">
                                    VALUE
                                  </TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody className="p-0">
                                {Object.keys(node["data"]["node"]["template"])
                                  .filter(
                                    (templateField) =>
                                      templateField.charAt(0) !== "_" &&
                                      node.data.node.template[templateField]
                                        .show &&
                                      LANGFLOW_SUPPORTED_TYPES.has(
                                        node.data.node.template[templateField]
                                          .type,
                                      ),
                                  )
                                  .map((templateField, indx) => {
                                    return (
                                      <TableRow key={indx} className="h-10">
                                        <TableCell className="p-0 text-center text-sm text-foreground">
                                          {templateField}
                                        </TableCell>
                                        <TableCell className="p-0 text-xs text-foreground">
                                          <div className="m-auto w-[250px]">
                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                  "str" &&
                                                !node.data.node.template[
                                                  templateField
                                                ].options
                                              }
                                            >
                                              <Case
                                                condition={
                                                  node.data.node.template[
                                                    templateField
                                                  ]?.list
                                                }
                                              >
                                                <InputListComponent
                                                  componentName={templateField}
                                                  editNode={true}
                                                  disabled={false}
                                                  value={
                                                    !node.data.node.template[
                                                      templateField
                                                    ].value ||
                                                    node.data.node.template[
                                                      templateField
                                                    ].value === ""
                                                      ? [""]
                                                      : node.data.node.template[
                                                          templateField
                                                        ].value
                                                  }
                                                  onChange={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks?.buildTweakObject!(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ],
                                                    );
                                                  }}
                                                />
                                              </Case>

                                              <Case
                                                condition={
                                                  node.data.node.template[
                                                    templateField
                                                  ].multiline
                                                }
                                              >
                                                <div>
                                                  <TextAreaComponent
                                                    disabled={false}
                                                    editNode={true}
                                                    value={
                                                      !node.data.node.template[
                                                        templateField
                                                      ].value ||
                                                      node.data.node.template[
                                                        templateField
                                                      ].value === ""
                                                        ? ""
                                                        : node.data.node
                                                            .template[
                                                            templateField
                                                          ].value
                                                    }
                                                    onChange={(target) => {
                                                      setData((old) => {
                                                        let newInputList =
                                                          cloneDeep(old);
                                                        newInputList![
                                                          i
                                                        ].data.node.template[
                                                          templateField
                                                        ].value = target;
                                                        return newInputList;
                                                      });
                                                      tweaks?.buildTweakObject!(
                                                        node["data"]["id"],
                                                        target,
                                                        node.data.node.template[
                                                          templateField
                                                        ],
                                                      );
                                                    }}
                                                  />
                                                </div>
                                              </Case>

                                              <Case
                                                condition={
                                                  !node.data.node.template[
                                                    templateField
                                                  ].multiline &&
                                                  !node.data.node.template[
                                                    templateField
                                                  ].list
                                                }
                                              >
                                                <InputComponent
                                                  editNode={true}
                                                  disabled={false}
                                                  password={
                                                    node.data.node.template[
                                                      templateField
                                                    ].password ?? false
                                                  }
                                                  value={
                                                    !node.data.node.template[
                                                      templateField
                                                    ].value ||
                                                    node.data.node.template[
                                                      templateField
                                                    ].value === ""
                                                      ? ""
                                                      : node.data.node.template[
                                                          templateField
                                                        ].value
                                                  }
                                                  onChange={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks?.buildTweakObject!(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ],
                                                    );
                                                  }}
                                                />
                                              </Case>
                                            </Case>

                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                "bool"
                                              }
                                            >
                                              <div className="ml-auto">
                                                {" "}
                                                <ToggleShadComponent
                                                  enabled={
                                                    node.data.node.template[
                                                      templateField
                                                    ].value
                                                  }
                                                  setEnabled={(e) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = e;
                                                      return newInputList;
                                                    });
                                                    tweaks?.buildTweakObject!(
                                                      node["data"]["id"],
                                                      e,
                                                      node.data.node.template[
                                                        templateField
                                                      ],
                                                    );
                                                  }}
                                                  size="small"
                                                  disabled={false}
                                                />
                                              </div>
                                            </Case>

                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                "file"
                                              }
                                            >
                                              <div className="mx-auto">
                                                <InputFileComponent
                                                  editNode={true}
                                                  disabled={false}
                                                  value={
                                                    node.data.node.template[
                                                      templateField
                                                    ].value ?? ""
                                                  }
                                                  onChange={(target: any) => {}}
                                                  fileTypes={
                                                    node.data.node.template[
                                                      templateField
                                                    ].fileTypes
                                                  }
                                                  onFileChange={(
                                                    value: any,
                                                  ) => {
                                                    node.data.node.template[
                                                      templateField
                                                    ].file_path = value;
                                                  }}
                                                ></InputFileComponent>
                                              </div>
                                            </Case>

                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                "float"
                                              }
                                            >
                                              <div className="mx-auto">
                                                <FloatComponent
                                                  disabled={false}
                                                  editNode={true}
                                                  value={
                                                    !node.data.node.template[
                                                      templateField
                                                    ].value ||
                                                    node.data.node.template[
                                                      templateField
                                                    ].value === ""
                                                      ? ""
                                                      : node.data.node.template[
                                                          templateField
                                                        ].value
                                                  }
                                                  rangeSpec={
                                                    node.data.node.template[
                                                      templateField
                                                    ].rangeSpec
                                                  }
                                                  onChange={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks?.buildTweakObject!(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ],
                                                    );
                                                  }}
                                                />
                                              </div>
                                            </Case>

                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                  "str" &&
                                                node.data.node.template[
                                                  templateField
                                                ].options
                                              }
                                            >
                                              <div className="mx-auto">
                                                <Dropdown
                                                  editNode={true}
                                                  options={
                                                    node.data.node.template[
                                                      templateField
                                                    ].options
                                                  }
                                                  onSelect={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks?.buildTweakObject!(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ],
                                                    );
                                                  }}
                                                  value={
                                                    !node.data.node.template[
                                                      templateField
                                                    ].value ||
                                                    node.data.node.template[
                                                      templateField
                                                    ].value === ""
                                                      ? ""
                                                      : node.data.node.template[
                                                          templateField
                                                        ].value
                                                  }
                                                ></Dropdown>
                                              </div>
                                            </Case>

                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                "int"
                                              }
                                            >
                                              <div className="mx-auto">
                                                <IntComponent
                                                  disabled={false}
                                                  editNode={true}
                                                  rangeSpec={
                                                    node.data.node.template[
                                                      templateField
                                                    ].rangeSpec
                                                  }
                                                  value={
                                                    !node.data.node.template[
                                                      templateField
                                                    ].value ||
                                                    node.data.node.template[
                                                      templateField
                                                    ].value === ""
                                                      ? ""
                                                      : node.data.node.template[
                                                          templateField
                                                        ].value
                                                  }
                                                  onChange={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks?.buildTweakObject!(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ],
                                                    );
                                                  }}
                                                />
                                              </div>
                                            </Case>

                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                "prompt"
                                              }
                                            >
                                              <div className="mx-auto">
                                                <PromptAreaComponent
                                                  readonly={true}
                                                  editNode={true}
                                                  disabled={false}
                                                  value={
                                                    !node.data.node.template[
                                                      templateField
                                                    ].value ||
                                                    node.data.node.template[
                                                      templateField
                                                    ].value === ""
                                                      ? ""
                                                      : node.data.node.template[
                                                          templateField
                                                        ].value
                                                  }
                                                  onChange={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks?.buildTweakObject!(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ],
                                                    );
                                                  }}
                                                />
                                              </div>
                                            </Case>

                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                "code"
                                              }
                                            >
                                              <div className="mx-auto">
                                                <CodeAreaComponent
                                                  disabled={false}
                                                  editNode={true}
                                                  readonly={true}
                                                  value={
                                                    !node.data.node.template[
                                                      templateField
                                                    ].value ||
                                                    node.data.node.template[
                                                      templateField
                                                    ].value === ""
                                                      ? ""
                                                      : node.data.node.template[
                                                          templateField
                                                        ].value
                                                  }
                                                  onChange={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks?.buildTweakObject!(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ],
                                                    );
                                                  }}
                                                />
                                              </div>
                                            </Case>

                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                "dict"
                                              }
                                            >
                                              <div className="mx-auto overflow-auto custom-scroll">
                                                <KeypairListComponent
                                                  disabled={false}
                                                  editNode={true}
                                                  value={
                                                    node.data.node!.template[
                                                      templateField
                                                    ].value?.length === 0 ||
                                                    !node.data.node!.template[
                                                      templateField
                                                    ].value
                                                      ? [{ "": "" }]
                                                      : convertObjToArray(
                                                          node.data.node!
                                                            .template[
                                                            templateField
                                                          ].value,
                                                          type(
                                                            node,
                                                            templateField,
                                                          ),
                                                        )
                                                  }
                                                  duplicateKey={
                                                    errorDuplicateKey
                                                  }
                                                  onChange={(target) => {
                                                    const valueToNumbers =
                                                      convertValuesToNumbers(
                                                        target,
                                                      );
                                                    node.data.node!.template[
                                                      templateField
                                                    ].value = valueToNumbers;
                                                    setErrorDuplicateKey(
                                                      hasDuplicateKeys(
                                                        valueToNumbers,
                                                      ),
                                                    );
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks?.buildTweakObject!(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ],
                                                    );
                                                  }}
                                                  isList={
                                                    node.data.node!.template[
                                                      templateField
                                                    ]?.list ?? false
                                                  }
                                                />
                                              </div>
                                            </Case>

                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                "NestedDict"
                                              }
                                            >
                                              <div className="mx-auto">
                                                <DictComponent
                                                  disabled={false}
                                                  editNode={true}
                                                  value={
                                                    node.data.node!.template[
                                                      templateField
                                                    ].value?.toString() === "{}"
                                                      ? {}
                                                      : node.data.node!
                                                          .template[
                                                          templateField
                                                        ].value
                                                  }
                                                  onChange={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks?.buildTweakObject!(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ],
                                                    );
                                                  }}
                                                />
                                              </div>
                                            </Case>

                                            <Case
                                              condition={
                                                type(node, templateField) ===
                                                "Any"
                                              }
                                            >
                                              <>-</>
                                            </Case>
                                          </div>
                                        </TableCell>
                                      </TableRow>
                                    );
                                  })}
                              </TableBody>
                            </Table>
                          </div>
                        </AccordionComponent>
                      )}

                      {tweaks?.tweaksList!.length === 0 && (
                        <>
                          <div className="pt-3">
                            No tweaks are available for this flow.
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </TabsContent>
      ))}
    </Tabs>
  );
}
