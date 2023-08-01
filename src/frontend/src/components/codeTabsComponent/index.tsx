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
        {Number(activeTab) < 4 && (
          <div className="float-right mx-1 flex gap-2">
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
                  {data.map((t: any, index) => (
                    <div className="px-3" key={index}>
                      {tweaks.tweaksList.current.includes(t["data"]["id"]) && (
                        <AccordionComponent
                          trigger={t["data"]["id"]}
                          open={openAccordion}
                          keyValue={t["data"]["id"]}
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
                                {Object.keys(t["data"]["node"]["template"])
                                  .filter(
                                    (n) =>
                                      n.charAt(0) !== "_" &&
                                      t.data.node.template[n].show &&
                                      (t.data.node.template[n].type === "str" ||
                                        t.data.node.template[n].type ===
                                          "bool" ||
                                        t.data.node.template[n].type ===
                                          "float" ||
                                        t.data.node.template[n].type ===
                                          "code" ||
                                        t.data.node.template[n].type ===
                                          "prompt" ||
                                        t.data.node.template[n].type ===
                                          "file" ||
                                        t.data.node.template[n].type === "int")
                                  )
                                  .map((n, i) => {
                                    return (
                                      <TableRow
                                        key={i}
                                        className="h-10 dark:border-b-muted"
                                      >
                                        <TableCell className="p-0 text-center text-sm text-foreground">
                                          {n}
                                        </TableCell>
                                        <TableCell className="p-0 text-xs text-foreground">
                                          <div className="m-auto w-[250px]">
                                            {t.data.node.template[n].type ===
                                              "str" &&
                                            !t.data.node.template[n].options ? (
                                              <div className="mx-auto">
                                                {t.data.node.template[n]
                                                  .list ? (
                                                  <InputListComponent
                                                    editNode={true}
                                                    disabled={false}
                                                    value={
                                                      !t.data.node.template[n]
                                                        .value ||
                                                      t.data.node.template[n]
                                                        .value === ""
                                                        ? [""]
                                                        : t.data.node.template[
                                                            n
                                                          ].value
                                                    }
                                                    onChange={(k) => {
                                                      setData((old) => {
                                                        let newInputList =
                                                          cloneDeep(old);
                                                        newInputList[
                                                          index
                                                        ].data.node.template[
                                                          n
                                                        ].value = k;
                                                        return newInputList;
                                                      });
                                                      tweaks.buildTweakObject(
                                                        t["data"]["id"],
                                                        k,
                                                        t.data.node.template[n]
                                                      );
                                                    }}
                                                  />
                                                ) : t.data.node.template[n]
                                                    .multiline ? (
                                                  <ShadTooltip
                                                    content={tweaks.buildContent(
                                                      t.data.node.template[n]
                                                        .value
                                                    )}
                                                  >
                                                    <div>
                                                      <TextAreaComponent
                                                        disabled={false}
                                                        editNode={true}
                                                        value={
                                                          !t.data.node.template[
                                                            n
                                                          ].value ||
                                                          t.data.node.template[
                                                            n
                                                          ].value === ""
                                                            ? ""
                                                            : t.data.node
                                                                .template[n]
                                                                .value
                                                        }
                                                        onChange={(k) => {
                                                          setData((old) => {
                                                            let newInputList =
                                                              cloneDeep(old);
                                                            newInputList[
                                                              index
                                                            ].data.node.template[
                                                              n
                                                            ].value = k;
                                                            return newInputList;
                                                          });
                                                          tweaks.buildTweakObject(
                                                            t["data"]["id"],
                                                            k,
                                                            t.data.node
                                                              .template[n]
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
                                                      t.data.node.template[n]
                                                        .password ?? false
                                                    }
                                                    value={
                                                      !t.data.node.template[n]
                                                        .value ||
                                                      t.data.node.template[n]
                                                        .value === ""
                                                        ? ""
                                                        : t.data.node.template[
                                                            n
                                                          ].value
                                                    }
                                                    onChange={(k) => {
                                                      setData((old) => {
                                                        let newInputList =
                                                          cloneDeep(old);
                                                        newInputList[
                                                          index
                                                        ].data.node.template[
                                                          n
                                                        ].value = k;
                                                        return newInputList;
                                                      });
                                                      tweaks.buildTweakObject(
                                                        t["data"]["id"],
                                                        k,
                                                        t.data.node.template[n]
                                                      );
                                                    }}
                                                  />
                                                )}
                                              </div>
                                            ) : t.data.node.template[n].type ===
                                              "bool" ? (
                                              <div className="ml-auto">
                                                {" "}
                                                <ToggleShadComponent
                                                  enabled={
                                                    t.data.node.template[n]
                                                      .value
                                                  }
                                                  setEnabled={(e) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList[
                                                        index
                                                      ].data.node.template[
                                                        n
                                                      ].value = e;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject(
                                                      t["data"]["id"],
                                                      e,
                                                      t.data.node.template[n]
                                                    );
                                                  }}
                                                  size="small"
                                                  disabled={false}
                                                />
                                              </div>
                                            ) : t.data.node.template[n].type ===
                                              "file" ? (
                                              <ShadTooltip
                                                content={tweaks.buildContent(
                                                  !t.data.node.template[n]
                                                    .value ||
                                                    t.data.node.template[n]
                                                      .value === ""
                                                    ? ""
                                                    : t.data.node.template[n]
                                                        .value
                                                )}
                                              >
                                                <div className="mx-auto">
                                                  <InputFileComponent
                                                    editNode={true}
                                                    disabled={false}
                                                    value={
                                                      t.data.node.template[n]
                                                        .value ?? ""
                                                    }
                                                    onChange={(k: any) => {}}
                                                    fileTypes={
                                                      t.data.node.template[n]
                                                        .fileTypes
                                                    }
                                                    suffixes={
                                                      t.data.node.template[n]
                                                        .suffixes
                                                    }
                                                    onFileChange={(
                                                      value: any
                                                    ) => {
                                                      t.data.node.template[
                                                        n
                                                      ].file_path = value;
                                                    }}
                                                  ></InputFileComponent>
                                                </div>
                                              </ShadTooltip>
                                            ) : t.data.node.template[n].type ===
                                              "float" ? (
                                              <div className="mx-auto">
                                                <FloatComponent
                                                  disabled={false}
                                                  editNode={true}
                                                  value={
                                                    !t.data.node.template[n]
                                                      .value ||
                                                    t.data.node.template[n]
                                                      .value === ""
                                                      ? ""
                                                      : t.data.node.template[n]
                                                          .value
                                                  }
                                                  onChange={(k) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList[
                                                        index
                                                      ].data.node.template[
                                                        n
                                                      ].value = k;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject(
                                                      t["data"]["id"],
                                                      k,
                                                      t.data.node.template[n]
                                                    );
                                                  }}
                                                />
                                              </div>
                                            ) : t.data.node.template[n].type ===
                                                "str" &&
                                              t.data.node.template[n]
                                                .options ? (
                                              <div className="mx-auto">
                                                <Dropdown
                                                  editNode={true}
                                                  apiModal={true}
                                                  options={
                                                    t.data.node.template[n]
                                                      .options
                                                  }
                                                  onSelect={(k) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList[
                                                        index
                                                      ].data.node.template[
                                                        n
                                                      ].value = k;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject(
                                                      t["data"]["id"],
                                                      k,
                                                      t.data.node.template[n]
                                                    );
                                                  }}
                                                  value={
                                                    !t.data.node.template[n]
                                                      .value ||
                                                    t.data.node.template[n]
                                                      .value === ""
                                                      ? ""
                                                      : t.data.node.template[n]
                                                          .value
                                                  }
                                                ></Dropdown>
                                              </div>
                                            ) : t.data.node.template[n].type ===
                                              "int" ? (
                                              <div className="mx-auto">
                                                <IntComponent
                                                  disabled={false}
                                                  editNode={true}
                                                  value={
                                                    !t.data.node.template[n]
                                                      .value ||
                                                    t.data.node.template[n]
                                                      .value === ""
                                                      ? ""
                                                      : t.data.node.template[n]
                                                          .value
                                                  }
                                                  onChange={(k) => {
                                                    setData((old) => {
                                                      let newInputList =
                                                        cloneDeep(old);
                                                      newInputList[
                                                        index
                                                      ].data.node.template[
                                                        n
                                                      ].value = k;
                                                      return newInputList;
                                                    });
                                                    tweaks.buildTweakObject(
                                                      t["data"]["id"],
                                                      k,
                                                      t.data.node.template[n]
                                                    );
                                                  }}
                                                />
                                              </div>
                                            ) : t.data.node.template[n].type ===
                                              "prompt" ? (
                                              <ShadTooltip
                                                content={tweaks.buildContent(
                                                  !t.data.node.template[n]
                                                    .value ||
                                                    t.data.node.template[n]
                                                      .value === ""
                                                    ? ""
                                                    : t.data.node.template[n]
                                                        .value
                                                )}
                                              >
                                                <div className="mx-auto">
                                                  <PromptAreaComponent
                                                    editNode={true}
                                                    disabled={false}
                                                    value={
                                                      !t.data.node.template[n]
                                                        .value ||
                                                      t.data.node.template[n]
                                                        .value === ""
                                                        ? ""
                                                        : t.data.node.template[
                                                            n
                                                          ].value
                                                    }
                                                    onChange={(k) => {
                                                      setData((old) => {
                                                        let newInputList =
                                                          cloneDeep(old);
                                                        newInputList[
                                                          index
                                                        ].data.node.template[
                                                          n
                                                        ].value = k;
                                                        return newInputList;
                                                      });
                                                      tweaks.buildTweakObject(
                                                        t["data"]["id"],
                                                        k,
                                                        t.data.node.template[n]
                                                      );
                                                    }}
                                                  />
                                                </div>
                                              </ShadTooltip>
                                            ) : t.data.node.template[n].type ===
                                              "code" ? (
                                              <ShadTooltip
                                                content={tweaks.buildContent(
                                                  tweaks.getValue(
                                                    t.data.node.template[n]
                                                      .value,
                                                    t.data,
                                                    t.data.node.template[n]
                                                  )
                                                )}
                                              >
                                                <div className="mx-auto">
                                                  <CodeAreaComponent
                                                    disabled={false}
                                                    editNode={true}
                                                    value={
                                                      !t.data.node.template[n]
                                                        .value ||
                                                      t.data.node.template[n]
                                                        .value === ""
                                                        ? ""
                                                        : t.data.node.template[
                                                            n
                                                          ].value
                                                    }
                                                    onChange={(k) => {
                                                      setData((old) => {
                                                        let newInputList =
                                                          cloneDeep(old);
                                                        newInputList[
                                                          index
                                                        ].data.node.template[
                                                          n
                                                        ].value = k;
                                                        return newInputList;
                                                      });
                                                      tweaks.buildTweakObject(
                                                        t["data"]["id"],
                                                        k,
                                                        t.data.node.template[n]
                                                      );
                                                    }}
                                                  />
                                                </div>
                                              </ShadTooltip>
                                            ) : t.data.node.template[n].type ===
                                              "Any" ? (
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
