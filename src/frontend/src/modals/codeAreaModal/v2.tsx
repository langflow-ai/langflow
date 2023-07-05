import { useContext, useRef, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import 'ace-builds/src-noconflict/ace';
import { darkContext } from "../../contexts/darkContext";
import { postCustomComponent, postValidateCode } from "../../controllers/API";
import { alertContext } from "../../contexts/alertContext";
import { Button } from "../../components/ui/button";
import { CODE_PROMPT_DIALOG_SUBTITLE } from "../../constants";
import { APIClassType } from "../../types/api";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import TwoColumnsModal from "../twoColumnsModal";

export default function CodeAreaModal({
  value,
  setValue,
  nodeClass,
  setNodeClass,
  dynamic
}: {
  setValue: (value: string) => void;
  value: string;
  nodeClass: APIClassType;
  setNodeClass: (Class: APIClassType) => void;
  dynamic?: boolean;
}) {
  const [open, setOpen] = useState(true);
  const [code, setCode] = useState(value);
  const [loading, setLoading] = useState(false);
  const { dark } = useContext(darkContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const [activeTab, setActiveTab] = useState("0");
  const [error, setError] = useState<{ detail: { error: string, traceback: string } }>(null)
  const { closePopUp, setCloseEdit } = useContext(PopUpContext);
  const ref = useRef();
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        setCloseEdit("editcode");
        closePopUp();
      }, 300);
    }
  }
  console.log(dynamic);

  function handleClick() {
    setLoading(true);
    if (!dynamic) {
      postValidateCode(code)
        .then((apiReturn) => {
          setLoading(false);
          if (apiReturn.data) {
            let importsErrors = apiReturn.data.imports.errors;
            let funcErrors = apiReturn.data.function.errors;
            if (funcErrors.length === 0 && importsErrors.length === 0) {
              setSuccessData({
                title: "Code is ready to run",
              });
              // setValue(code);
            } else {
              if (funcErrors.length !== 0) {
                setErrorData({
                  title: "There is an error in your function",
                  list: funcErrors,
                });
              }
              if (importsErrors.length !== 0) {
                setErrorData({
                  title: "There is an error in your imports",
                  list: importsErrors,
                });
              }
            }
          } else {
            setErrorData({
              title: "Something went wrong, please try again",
            });
          }
        })
        .catch((_) => {
          setLoading(false);
          setErrorData({
            title: "There is something wrong with this code, please review it",
          });
        });
    }
    else {
      postCustomComponent(code, nodeClass).then((apiReturn) => {
        const { data } = apiReturn;
        if (data) {
          setNodeClass(data);
          setModalOpen(false);
        }
      }).catch((err) => {
        setErrorData({
          title: "There is something wrong with this code, please see the error on the errors tab",
        });
        console.log(err.response.data);
        setError(err.response.data);
      });
    }

  }
  const tabs = [{ name: "code" }, { name: "errors" }]

  return (
    <TwoColumnsModal open={open} setOpen={setOpen}>
        <TwoColumnsModal.Header description={CODE_PROMPT_DIALOG_SUBTITLE}>{"A"}</TwoColumnsModal.Header>
        <TwoColumnsModal.First>{"A"}</TwoColumnsModal.First>
        <TwoColumnsModal.Second>{"B"}</TwoColumnsModal.Second>
    </TwoColumnsModal>
  );
}
