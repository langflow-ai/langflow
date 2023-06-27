import { useContext, useEffect, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import "ace-builds/src-noconflict/ext-language_tools";
// import "ace-builds/webpack-resolver";
import { darkContext } from "../../contexts/darkContext";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { FlowType } from "../../types/flow/index";
import { getCurlCode, getPythonApiCode, getPythonCode } from "../../constants";
import { EXPORT_CODE_DIALOG } from "../../constants";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import { Check, Clipboard, Code2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { buildTweaks, classNames, limitScrollFieldsModal } from "../../utils";
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
import ShadTooltip from "../../components/ShadTooltipComponent";

export default function ApiModal({ flow }: { flow: FlowType }) {
  const [open, setOpen] = useState(true);
  const { dark } = useContext(darkContext);
  const { closePopUp } = useContext(PopUpContext);
  const [activeTab, setActiveTab] = useState("0");
  const [isCopied, setIsCopied] = useState<Boolean>(false);
  const [enabled, setEnabled] = useState(null);
  const tweak = useRef([]);

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
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      closePopUp();
    }
  }
  

  const pythonApiCode = getPythonApiCode(flow, tweak.current);
  const curl_code = getCurlCode(flow, tweak.current);
  const pythonCode = getPythonCode(flow, tweak.current);
  const tweaksCode = buildTweaks(flow);

  const tabs = [
    {
      name: "cURL",
      mode: "bash",
      image: "https://curl.se/logo/curl-symbol-transparent.png",
      code: curl_code,
    },
    {
      name: "Python API",
      mode: "python",
      image:
        "https://images.squarespace-cdn.com/content/v1/5df3d8c5d2be5962e4f87890/1628015119369-OY4TV3XJJ53ECO0W2OLQ/Python+API+Training+Logo.png?format=1000w",
      code: pythonApiCode,
    },
    {
      name: "Python Code",
      mode: "python",
      image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
      code: pythonCode,
    },
  ];

  if (Object.keys(tweaksCode).length > 0) {
    tabs.push({
      name: "Tweaks",
      mode: "python",
      image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
      code: pythonCode,
    });
  }

  function buildTweakObject(tw, changes, template) {
    if (template.type === "float") {
      changes = parseFloat(changes);
    }
    if (template.type === "int") {
      changes = parseInt(changes);
    }
    if (template.list === true && Array.isArray(changes)) {
      changes = changes?.filter((x) => x !== "");
    }

    const existingTweak = tweak.current.find((element) =>
      element.hasOwnProperty(tw)
    );

    if (existingTweak) {
      existingTweak[tw][template["name"]] = changes;

      if (template.list === true) {
        if (changes.length === 0) {
          if (existingTweak[tw] && existingTweak[tw][template["name"]]) {
            delete existingTweak[tw][template["name"]];
          }
        }
      }

      if (existingTweak[tw][template["name"]] == template.value) {
        tweak.current.forEach((element) => {
          if (element[tw] && element[tw][template["name"]]) {
            delete element[tw][template["name"]];
          }
          if (element[tw] && Object.keys(element[tw])?.length === 0) {
            tweak.current = tweak.current.filter((obj) => {
              const prop = obj[Object.keys(obj)[0]].prop;
              return prop !== undefined && prop !== null && prop !== "";
            });
            delete element[tw];
          }
        });
      }
    } else {
      const newTweak = {
        [tw]: {
          [template["name"]]: changes,
        },
      };
      tweak.current.push(newTweak);
    }

    const pythonApiCode = getPythonApiCode(flow, tweak.current);
    const curl_code = getCurlCode(flow, tweak.current);
    const pythonCode = getPythonCode(flow, tweak.current);

    tabs[0].code = curl_code;
    tabs[1].code = pythonApiCode;
    tabs[2].code = pythonCode;

    console.log(tweak.current);
  }

  function buildContent(value) {
    const htmlContent = (
      <div className="w-[200px]">
        <span>{value != null && value != '' ? value : 'None'}</span>
      </div>
    );
    return htmlContent;
  }

  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger></DialogTrigger>
      <DialogContent className="lg:max-w-[850px] sm:max-w-[700px] h-[580px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">Code</span>
            <Code2
              className="h-6 w-6 text-gray-800 pl-1 dark:text-white"
              aria-hidden="true"
            />
          </DialogTitle>
          <DialogDescription>{EXPORT_CODE_DIALOG}</DialogDescription>
        </DialogHeader>

        <Tabs
          defaultValue={"0"}
          className="w-full h-full overflow-hidden text-center bg-muted rounded-md border"
          onValueChange={(value) => setActiveTab(value)}
        >
          <div className="flex items-center justify-between px-2">
            <TabsList>
              {tabs.map((tab, index) => (
                <TabsTrigger key={index} value={index.toString()}>
                  {tab.name}
                </TabsTrigger>
              ))}
            </TabsList>
            {Number(activeTab) < 3 && (
              <div className="float-right">
                <button
                  className="flex gap-1.5 items-center rounded bg-none p-1 text-xs text-gray-500 dark:text-gray-300"
                  onClick={copyToClipboard}
                >
                  {isCopied ? <Check size={18} /> : <Clipboard size={15} />}
                  {isCopied ? "Copied!" : "Copy code"}
                </button>
              </div>
            )}
          </div>

          {tabs.map((tab, index) => (
            <TabsContent
              value={index.toString()}
              className="overflow-hidden w-full h-full px-4 pb-4 -mt-1"
              key={index} // Remember to add a unique key prop
            >
              {index < 3 ? (
                <SyntaxHighlighter
                  className="h-[400px] w-full overflow-auto"
                  language={tab.mode}
                  style={oneDark}
                >
                  {tab.code}
                </SyntaxHighlighter>
              ) : index === 3 ? (
                <>
                  <div className="flex w-full h-[400px] mt-2">
                    <div
                      className={classNames(
                        "w-full rounded-lg  bg-muted border-[1px] border-gray-200",
                        1 == 1
                          ? "overflow-scroll overflow-x-hidden custom-scroll"
                          : "overflow-hidden"
                      )}
                    >
                      {flow["data"]["nodes"].map((t: any, index) => (
                        <div className="px-3">
                          <AccordionComponent trigger={t["data"]["id"]}>
                            <div className="flex flex-col gap-5 h-fit">
                              <Table className="table-fixed bg-muted outline-1">
                                <TableHeader className="border-gray-200 text-gray-500 text-xs font-medium h-10">
                                  <TableRow className="dark:border-b-muted">
                                    <TableHead className="h-7 text-center">
                                      PARAM
                                    </TableHead>
                                    <TableHead className="p-0 h-7 text-center">
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
                                        (t.data.node.template[n].type ===
                                          "str" ||
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
                                          t.data.node.template[n].type ===
                                            "int")
                                    )
                                    .map((n, i) => {
                                      // console.log(t.data.node.template[n]);

                                      return (
                                        <TableRow
                                          key={i}
                                          className="h-10 dark:border-b-muted"
                                        >
                                          <TableCell className="p-0 text-center text-gray-900 text-sm">
                                            {n}
                                          </TableCell>
                                          <TableCell className="p-0 text-center text-gray-900 text-xs dark:text-gray-300">
                                            <div className="w-[250px] m-auto">
                                              {t.data.node.template[n].type ===
                                                "str" &&
                                              !t.data.node.template[n]
                                                .options ? (
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
                                                          : t.data.node
                                                              .template[n].value
                                                      }
                                                      onChange={(k) => {}}
                                                      onAddInput={(k) => {
                                                        buildTweakObject(
                                                          t["data"]["id"],
                                                          k,
                                                          t.data.node.template[
                                                            n
                                                          ]
                                                        );
                                                      }}
                                                    />
                                                  ) : t.data.node.template[n]
                                                      .multiline ? (
                                                    <div>
                                                      <ShadTooltip
                                                        delayDuration={1000}
                                                        content={buildContent(
                                                          t.data.node.template[
                                                            n
                                                          ].value
                                                        )}
                                                      >
                                                        <TextAreaComponent
                                                          disabled={true}
                                                          editNode={true}
                                                          value={
                                                            t.data.node
                                                              .template[n]
                                                              .value ?? ""
                                                          }
                                                          onChange={(k) => {}}
                                                        />
                                                      </ShadTooltip>
                                                    </div>
                                                  ) : (
                                                    <InputComponent
                                                      editNode={true}
                                                      disabled={false}
                                                      password={
                                                        t.data.node.template[n]
                                                          .password ?? false
                                                      }
                                                      value={
                                                        t.data.node.template[n]
                                                          .value ?? ""
                                                      }
                                                      onChange={(k) => {
                                                        buildTweakObject(
                                                          t["data"]["id"],
                                                          k,
                                                          t.data.node.template[
                                                            n
                                                          ]
                                                        );
                                                      }}
                                                    />
                                                  )}
                                                </div>
                                              ) : t.data.node.template[n]
                                                  .type === "bool" ? (
                                                <div className="ml-auto">
                                                  {" "}
                                                  <ToggleShadComponent
                                                    enabled={
                                                      t.data.node.template[n]
                                                        .value
                                                    }
                                                    setEnabled={(e) => {
                                                      t.data.node.template[
                                                        n
                                                      ].value = e;
                                                      setEnabled(e);
                                                      buildTweakObject(
                                                        t["data"]["id"],
                                                        e,
                                                        t.data.node.template[n]
                                                      );
                                                    }}
                                                    size="small"
                                                    disabled={false}
                                                  />
                                                </div>
                                              )
                                              :
                                              t.data.node.template[n]
                                                  .type === "file" ? (
                                                    <ShadTooltip
                                                    delayDuration={1000}
                                                    content={buildContent(
                                                      t.data.node.template[n]
                                                        .value
                                                    )}
                                                  >
                                                  <div className="mx-auto">
                                                  <InputFileComponent
                                                    editNode={true}
                                                    disabled={true}
                                                    value={
                                                      t.data.node.template[n]
                                                        .value ?? ""
                                                    }
                                                    onChange={(k: any) => {

                                                    }}
                                                    fileTypes={
                                                      t.data.node.template[n]
                                                        .fileTypes
                                                    }
                                                    suffixes={
                                                      t.data.node.template[n]
                                                        .suffixes
                                                    }
                                                    onFileChange={(k: any) => {
                                                    }}
                                                  ></InputFileComponent>
                                                </div>
                                                    </ShadTooltip>

                                              )
                                              : t.data.node.template[n]
                                                  .type === "float" ? (
                                                <div className="mx-auto">
                                                  <FloatComponent
                                                    disabled={false}
                                                    editNode={true}
                                                    value={
                                                      t.data.node.template[n]
                                                        .value ?? ""
                                                    }
                                                    onChange={(k) => {
                                                      buildTweakObject(
                                                        t["data"]["id"],
                                                        k,
                                                        t.data.node.template[n]
                                                      );
                                                    }}
                                                  />
                                                </div>
                                              ) : t.data.node.template[n]
                                                  .type === "str" &&
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
                                                    onSelect={(k) =>
                                                      buildTweakObject(
                                                        t["data"]["id"],
                                                        k,
                                                        t.data.node.template[n]
                                                      )
                                                    }
                                                    value={
                                                      t.data.node.template[n]
                                                        .value ??
                                                      "Choose an option"
                                                    }
                                                  ></Dropdown>
                                                </div>
                                              ) : t.data.node.template[n]
                                                  .type === "int" ? (
                                                <div className="mx-auto">
                                                  <IntComponent
                                                    disabled={false}
                                                    editNode={true}
                                                    value={
                                                      t.data.node.template[n]
                                                        .value ?? ""
                                                    }
                                                    onChange={(k) => {
                                                      buildTweakObject(
                                                        t["data"]["id"],
                                                        k,
                                                        t.data.node.template[n]
                                                      );
                                                    }}
                                                  />
                                                </div>
                                              ) : t.data.node.template[n]
                                                  .type === "prompt" ? (
                                                <ShadTooltip
                                                  delayDuration={1000}
                                                  content={buildContent(
                                                    t.data.node.template[n]
                                                      .value
                                                  )}
                                                >
                                                  <div className="mx-auto">
                                                    <PromptAreaComponent
                                                      editNode={true}
                                                      disabled={true}
                                                      value={
                                                        t.data.node.template[n]
                                                          .value ?? ""
                                                      }
                                                      onChange={(k) => {}}
                                                    />
                                                  </div>
                                                </ShadTooltip>
                                              ) : t.data.node.template[n]
                                                  .type === "code" ? (
                                                <ShadTooltip
                                                  delayDuration={1000}
                                                  content={buildContent(
                                                    t.data.node.template[n]
                                                      .value
                                                  )}
                                                >
                                                  <div className="mx-auto">
                                                    <CodeAreaComponent
                                                      disabled={true}
                                                      editNode={true}
                                                      value={
                                                        t.data.node.template[n]
                                                          .value ?? ""
                                                      }
                                                      onChange={(k) => {}}
                                                    />
                                                  </div>
                                                </ShadTooltip>
                                              ) : t.data.node.template[n]
                                                  .type === "Any" ? (
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
                        </div>
                      ))}

                      {/* 
                      <div className="flex flex-col gap-5 bg-muted">
                        <Table className="table-fixed bg-muted outline-1">
                          <TableHeader className="border-gray-200 text-gray-500 text-xs font-medium h-10">
                            <TableRow className="dark:border-b-muted">
                              <TableHead className="h-5 text-center">
                                TWEAK
                              </TableHead>
                              <TableHead className="p-0 h-5 text-center">
                                VALUE
                              </TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {invoices.map((invoice) => (
                              <TableRow className="p-0 text-center text-gray-900 text-sm">
                                <TableCell className="p-2 text-center text-gray-900 text-sm truncate">
                                  {invoice.paymentStatus}
                                </TableCell>
                                <TableCell className="p-2 text-center text-gray-900 text-sm truncate">
                                  {invoice.paymentMethod}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div> */}
                    </div>
                  </div>
                </>
              ) : null}
            </TabsContent>
          ))}
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
