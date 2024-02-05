import { cloneDeep } from "lodash";
import { useContext, useEffect, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import AccordionComponent from "../../components/AccordionComponent";
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
import { LANGFLOW_SUPPORTED_TYPES } from "../../constants/constants";
import { darkContext } from "../../contexts/darkContext";
import { typesContext } from "../../contexts/typesContext";
import { codeTabsPropsType } from "../../types/components";
import {
  convertObjToArray,
  convertValuesToNumbers,
  hasDuplicateKeys,
  unselectAllNodes,
} from "../../utils/reactflowUtils";
import { classNames } from "../../utils/utils";
import DictComponent from "../dictComponent";
import IconComponent from "../genericIconComponent";
import KeypairListComponent from "../keypairListComponent";

export default function CodeTabsComponent({
  flow,
  tabs,
  activeTab,
  setActiveTab,
  isMessage,
  tweaks,
}: codeTabsPropsType) {
  const [isCopied, setIsCopied] = useState<Boolean>(false);
  const [data, setData] = useState(flow ? flow["data"]!["nodes"] : null);
  const [openAccordion, setOpenAccordion] = useState<string[]>([]);
  const { dark } = useContext(darkContext);
  const { reactFlowInstance } = useContext(typesContext);
  const [errorDuplicateKey, setErrorDuplicateKey] = useState(false);

  useEffect(() => {
    if (flow && flow["data"]!["nodes"]) {
      setData(flow["data"]!["nodes"]);
    }
  }, [flow]);

  useEffect(() => {
    if (tweaks && data) {
      unselectAllNodes({
        data,
        updateNodes: (nodes) => {
          reactFlowInstance?.setNodes(nodes);
        },
      });
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
    let accordionsToOpen: string[] = [];
    tweaks?.tweak!.current.forEach((el) => {
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

      {tabs.map((tab, idx) => (
        <TabsContent
          value={idx.toString()}
          className="api-modal-tabs-content"
          key={idx} // Remember to add a unique key prop
        >
          {idx < 4 ? (
            <div className="flex h-full w-full flex-col">
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
            </div>
          ) : idx === 4 ? (
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
                  {data?.map((node: any, i) => (
                    <div className="px-3" key={i}>
                      {tweaks?.tweaksList!.current.includes(
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
                                      LANGFLOW_SUPPORTED_TYPES.has(
                                        node.data.node.template[templateField]
                                          .type
                                      )
                                  )
                                  .map((templateField, indx) => {
                                    return (
                                      <TableRow
                                        key={indx}
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
                                                        newInputList![
                                                          i
                                                        ].data.node.template[
                                                          templateField
                                                        ].value = target;
                                                        return newInputList;
                                                      });
                                                      tweaks.buildTweakObject!(
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
                                                  <div>
                                                    <TextAreaComponent
                                                      disabled={false}
                                                      editNode={true}
                                                      value={
                                                        !node.data.node
                                                          .template[
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
                                                        tweaks.buildTweakObject!(
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
                                                        newInputList![
                                                          i
                                                        ].data.node.template[
                                                          templateField
                                                        ].value = target;
                                                        return newInputList;
                                                      });
                                                      tweaks.buildTweakObject!(
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
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = e;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject!(
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
                                                    value: any
                                                  ) => {
                                                    node.data.node.template[
                                                      templateField
                                                    ].file_path = value;
                                                  }}
                                                ></InputFileComponent>
                                              </div>
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
                                                    tweaks.buildTweakObject!(
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
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject!(
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
                                                      newInputList![
                                                        i
                                                      ].data.node.template[
                                                        templateField
                                                      ].value = target;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject!(
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
                                              <div className="mx-auto">
                                                <PromptAreaComponent
                                                  readonly={
                                                    node.data.node?.flow &&
                                                    node.data.node.template[
                                                      templateField
                                                    ].dynamic
                                                      ? true
                                                      : false
                                                  }
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
                                                    tweaks.buildTweakObject!(
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
                                              ].type === "code" ? (
                                              <div className="mx-auto">
                                                <CodeAreaComponent
                                                  disabled={false}
                                                  editNode={true}
                                                  readonly={
                                                    node.data.node?.flow &&
                                                    node.data.node.template[
                                                      templateField
                                                    ].dynamic
                                                      ? true
                                                      : false
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
                                                    tweaks.buildTweakObject!(
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
                                              ].type === "dict" ? (
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
                                                          ].value
                                                        )
                                                  }
                                                  duplicateKey={
                                                    errorDuplicateKey
                                                  }
                                                  onChange={(target) => {
                                                    const valueToNumbers =
                                                      convertValuesToNumbers(
                                                        target
                                                      );
                                                    node.data.node!.template[
                                                      templateField
                                                    ].value = valueToNumbers;
                                                    setErrorDuplicateKey(
                                                      hasDuplicateKeys(
                                                        valueToNumbers
                                                      )
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
                                                    tweaks.buildTweakObject!(
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
                                              ].type === "NestedDict" ? (
                                              <div className="mx-auto">
                                                <DictComponent
                                                  disabled={false}
                                                  editNode={true}
                                                  value={
                                                    node.data.node!.template[
                                                      templateField
                                                    ].value.toString() === "{}"
                                                      ? {
                                                          yourkey: "value",
                                                        }
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
                                                    tweaks.buildTweakObject!(
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

                      {tweaks?.tweaksList!.current.length === 0 && (
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
