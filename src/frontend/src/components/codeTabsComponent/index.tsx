import { cloneDeep } from "lodash";
import { useContext, useEffect, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import AccordionComponent from "../../components/AccordionComponent";
import ShadTooltip from "../../components/ShadTooltipComponent";
import CodeAreaComponent from "../../components/codeAreaComponent";
import Dropdown from "../../components/dropdownComponent";
import FloatComponent from "../../components/floatComponent";
import InputComponent from "../../components/inputComponent";
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
import { darkContext } from "../../contexts/darkContext";
import { FlowType } from "../../types/flow/index";
import { classNames } from "../../utils/utils";
import IconComponent from "../genericIconComponent";

export default function CodeTabsComponent({
  flow,
  tabs,
  activeTab,
  setActiveTab,
  isMessage,
  tweaks,
}: {
  flow?: FlowType;
  tabs: any;
  activeTab: string;
  setActiveTab: any;
  isMessage?: boolean;
  tweaks?: {
    tweak?: any;
    tweaksList?: any;
    buildContent?: any;
    getValue?: any;
    buildTweakObject?: any;
  };
}) {
  const [isCopied, setIsCopied] = useState<Boolean>(false);
  const [data, setData] = useState(flow ? flow["data"]["nodes"] : null);
  const [openAccordion, setOpenAccordion] = useState([]);
  const { dark } = useContext(darkContext);

  useEffect(() => {
    if (flow && flow["data"]["nodes"]) {
      setData(flow["data"]["nodes"]);
    }
  }, [flow]);

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

  const downloadAsFile = () => {
    const fileExtension = tabs[activeTab].language || ".txt";
    const suggestedFileName = `${"generated-code."}${fileExtension}`;
    const fileName = window.prompt("Enter the file name.", suggestedFileName);

    if (!fileName) {
      // user pressed cancel on prompt
      return;
    }

    const blob = new Blob([tabs[activeTab].code], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.download = fileName;
    link.href = url;
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  function openAccordions() {
    let accordionsToOpen = [];
    tweaks.tweak.current.forEach((el) => {
      Object.keys(el).forEach((key) => {
        if (Object.keys(el[key]).length > 0) {
          accordionsToOpen.push(key);
          setOpenAccordion(accordionsToOpen);
        }
      });
    });

    if (accordionsToOpen.length == 0) {
      setOpenAccordion([]);
    }
  }
  return (
    <Tabs
      value={activeTab}
      className={
        "api-modal-tabs " +
        (isMessage ? "dark " : "") +
        (dark && isMessage ? "bg-background" : "")
      }
      onValueChange={(value) => {
        setActiveTab(value);
        if (value === "3") {
          openAccordions();
        }
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
        {Number(activeTab) < 4 && (
          <div className="float-right mx-1 mb-1 mt-2 flex gap-2">
            <button
              className="flex items-center gap-1.5 rounded bg-none p-1 text-xs text-gray-500 dark:text-gray-300"
              onClick={copyToClipboard}
            >
              {isCopied ? (
                <IconComponent name="Check" className="h-4 w-4" />
              ) : (
                <IconComponent name="Clipboard" className="h-4 w-4" />
              )}
              {isCopied ? "Copied!" : "Copy code"}
            </button>
            <button
              className="flex items-center gap-1.5 rounded bg-none p-1 text-xs text-gray-500 dark:text-gray-300"
              onClick={downloadAsFile}
            >
              <IconComponent name="Download" className="h-5 w-5" />
            </button>
          </div>
        )}
      </div>

      {tabs.map((tab, index) => (
        <TabsContent
          value={index.toString()}
          className="api-modal-tabs-content"
          key={index} // Remember to add a unique key prop
        >
          {index < 4 ? (
            <>
              {tab.description && (
                <div
                  className="mb-2 w-full text-left text-sm"
                  dangerouslySetInnerHTML={{ __html: tab.description }}
                ></div>
              )}
              <SyntaxHighlighter
                className="mt-0 h-full w-full overflow-auto custom-scroll"
                language={tab.mode}
                style={oneDark}
              >
                {tab.code}
              </SyntaxHighlighter>
            </>
          ) : index === 4 ? (
            <>
              <div className="api-modal-according-display">
                <div
                  className={classNames(
                    "h-[70vh] w-full rounded-lg bg-muted",
                    1 == 1
                      ? "overflow-scroll overflow-x-hidden custom-scroll"
                      : "overflow-hidden"
                  )}
                >
                  {data.map((node: any, index) => (
                    <div className="px-3" key={index}>
                      {tweaks.tweaksList.current.includes(
                        node["data"]["id"]
                      ) && (
                        <AccordionComponent
                          trigger={node["data"]["id"]}
                          open={openAccordion}
                          keyValue={node["data"]["id"]}
                        >
                          <div className="api-modal-table-arrangement">
                            <Table className="table-fixed bg-muted outline-1">
                              <TableHeader className="h-10 border-input text-xs font-medium text-ring">
                                <TableRow className="dark:border-b-muted">
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
                                      (node.data.node.template[templateField]
                                        .type === "str" ||
                                        node.data.node.template[templateField]
                                          .type === "bool" ||
                                        node.data.node.template[templateField]
                                          .type === "float" ||
                                        node.data.node.template[templateField]
                                          .type === "code" ||
                                        node.data.node.template[templateField]
                                          .type === "prompt" ||
                                        node.data.node.template[templateField]
                                          .type === "file" ||
                                        node.data.node.template[templateField]
                                          .type === "int")
                                  )
                                  .map((templateField, index) => {
                                    return (
                                      <TableRow
                                        key={index}
                                        className="h-10 dark:border-b-muted"
                                      >
                                        <TableCell className="p-0 text-center text-sm text-foreground">
                                          {templateField}
                                        </TableCell>
                                        <TableCell className="p-0 text-xs text-foreground">
                                          <div className="m-auto w-[250px]">
                                            {node.data.node.template[
                                              templateField
                                            ].type === "str" &&
                                            !node.data.node.template[
                                              templateField
                                            ].options ? (
                                              <div className="mx-auto">
                                                {node.data.node.template[
                                                  templateField
                                                ].list ? (
                                                  <InputListComponent
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
                                                        : node.data.node
                                                            .template[
                                                            templateField
                                                          ].value
                                                    }
                                                    onChange={(target) => {
                                                      setData((old) => {
                                                        let newInputList =
                                                          cloneDeep(old);
                                                        newInputList[
                                                          index
                                                        ].data.node.template[
                                                          templateField
                                                        ].value = target;
                                                        return newInputList;
                                                      });
                                                      tweaks.buildTweakObject(
                                                        node["data"]["id"],
                                                        target,
                                                        node.data.node.template[
                                                          templateField
                                                        ]
                                                      );
                                                    }}
                                                  />
                                                ) : node.data.node.template[
                                                    templateField
                                                  ].multiline ? (
                                                  <ShadTooltip
                                                    content={tweaks.buildContent(
                                                      node.data.node.template[
                                                        templateField
                                                      ].value
                                                    )}
                                                  >
                                                    <div>
                                                      <TextAreaComponent
                                                        disabled={false}
                                                        editNode={true}
                                                        value={
                                                          !node.data.node
                                                            .template[
                                                            templateField
                                                          ].value ||
                                                          node.data.node
                                                            .template[
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
                                                            newInputList[
                                                              index
                                                            ].data.node.template[
                                                              templateField
                                                            ].value = target;
                                                            return newInputList;
                                                          });
                                                          tweaks.buildTweakObject(
                                                            node["data"]["id"],
                                                            target,
                                                            node.data.node
                                                              .template[
                                                              templateField
                                                            ]
                                                          );
                                                        }}
                                                      />
                                                    </div>
                                                  </ShadTooltip>
                                                ) : (
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
                                                        : node.data.node
                                                            .template[
                                                            templateField
                                                          ].value
                                                    }
                                                    onChange={(target) => {
                                                      setData((old) => {
                                                        let newInputList =
                                                          cloneDeep(old);
                                                        newInputList[
                                                          index
                                                        ].data.node.template[
                                                          templateField
                                                        ].value = target;
                                                        return newInputList;
                                                      });
                                                      tweaks.buildTweakObject(
                                                        node["data"]["id"],
                                                        target,
                                                        node.data.node.template[
                                                          templateField
                                                        ]
                                                      );
                                                    }}
                                                  />
                                                )}
                                              </div>
                                            ) : node.data.node.template[
                                                templateField
                                              ].type === "bool" ? (
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
                                                      newInputList[
                                                        index
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = e;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject(
                                                      node["data"]["id"],
                                                      e,
                                                      node.data.node.template[
                                                        templateField
                                                      ]
                                                    );
                                                  }}
                                                  size="small"
                                                  disabled={false}
                                                />
                                              </div>
                                            ) : node.data.node.template[
                                                templateField
                                              ].type === "file" ? (
                                              <ShadTooltip
                                                content={tweaks.buildContent(
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
                                                )}
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
                                                    onChange={(
                                                      target: any
                                                    ) => {}}
                                                    fileTypes={
                                                      node.data.node.template[
                                                        templateField
                                                      ].fileTypes
                                                    }
                                                    suffixes={
                                                      node.data.node.template[
                                                        templateField
                                                      ].suffixes
                                                    }
                                                    onFileChange={(
                                                      value: any
                                                    ) => {
                                                      node.data.node.template[
                                                        templateField
                                                      ].file_path = value;
                                                    }}
                                                  ></InputFileComponent>
                                                </div>
                                              </ShadTooltip>
                                            ) : node.data.node.template[
                                                templateField
                                              ].type === "float" ? (
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
                                                  onChange={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList[
                                                        index
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ]
                                                    );
                                                  }}
                                                />
                                              </div>
                                            ) : node.data.node.template[
                                                templateField
                                              ].type === "str" &&
                                              node.data.node.template[
                                                templateField
                                              ].options ? (
                                              <div className="mx-auto">
                                                <Dropdown
                                                  editNode={true}
                                                  apiModal={true}
                                                  options={
                                                    node.data.node.template[
                                                      templateField
                                                    ].options
                                                  }
                                                  onSelect={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList[
                                                        index
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ]
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
                                            ) : node.data.node.template[
                                                templateField
                                              ].type === "int" ? (
                                              <div className="mx-auto">
                                                <IntComponent
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
                                                  onChange={(target) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList[
                                                        index
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject(
                                                      node["data"]["id"],
                                                      target,
                                                      node.data.node.template[
                                                        templateField
                                                      ]
                                                    );
                                                  }}
                                                />
                                              </div>
                                            ) : node.data.node.template[
                                                templateField
                                              ].type === "prompt" ? (
                                              <ShadTooltip
                                                content={tweaks.buildContent(
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
                                                )}
                                              >
                                                <div className="mx-auto">
                                                  <PromptAreaComponent
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
                                                        : node.data.node
                                                            .template[
                                                            templateField
                                                          ].value
                                                    }
                                                    onChange={(target) => {
                                                      setData((old) => {
                                                        let newInputList =
                                                          cloneDeep(old);
                                                        newInputList[
                                                          index
                                                        ].data.node.template[
                                                          templateField
                                                        ].value = target;
                                                        return newInputList;
                                                      });
                                                      tweaks.buildTweakObject(
                                                        node["data"]["id"],
                                                        target,
                                                        node.data.node.template[
                                                          templateField
                                                        ]
                                                      );
                                                    }}
                                                  />
                                                </div>
                                              </ShadTooltip>
                                            ) : node.data.node.template[
                                                templateField
                                              ].type === "code" ? (
                                              <ShadTooltip
                                                content={tweaks.buildContent(
                                                  tweaks.getValue(
                                                    node.data.node.template[
                                                      templateField
                                                    ].value,
                                                    node.data,
                                                    node.data.node.template[
                                                      templateField
                                                    ]
                                                  )
                                                )}
                                              >
                                                <div className="mx-auto">
                                                  <CodeAreaComponent
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
                                                        newInputList[
                                                          index
                                                        ].data.node.template[
                                                          templateField
                                                        ].value = target;
                                                        return newInputList;
                                                      });
                                                      tweaks.buildTweakObject(
                                                        node["data"]["id"],
                                                        target,
                                                        node.data.node.template[
                                                          templateField
                                                        ]
                                                      );
                                                    }}
                                                  />
                                                </div>
                                              </ShadTooltip>
                                            ) : node.data.node.template[
                                                templateField
                                              ].type === "Any" ? (
                                              "-"
                                            ) : (
                                              <div className="hidden"></div>
                                            )}
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

                      {tweaks.tweaksList.current.length === 0 && (
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
