import { useContext, useEffect, useRef, useState } from "react";
import ShadTooltip from "../../components/ShadTooltipComponent";
import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { alertContext } from "../../contexts/alertContext";
import { AuthContext } from "../../contexts/authContext";
import { deleteApiKey, getApiKey } from "../../controllers/API";
import ConfirmationModal from "../../modals/ConfirmationModal";
import SecretKeyModal from "../../modals/SecretKeyModal";

import moment from "moment";

export default function ApiKeysPage() {
  const [loadingKeys, setLoadingKeys] = useState(true);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const { userData } = useContext(AuthContext);
  const [userId, setUserId] = useState("");
  const keysList = useRef([]);

  useEffect(() => {
    setTimeout(() => {
      getKeys();
    }, 500);
  }, [userData]);

  function getKeys() {
    setLoadingKeys(true);
    if (userData) {
      getApiKey(userData.id)
        .then((keys) => {
          keysList.current = keys["api_keys"];
          setUserId(keys["user_id"]);
          setLoadingKeys(false);
        })
        .catch((error) => {
          setLoadingKeys(false);
        });
    }
  }

  function resetFilter() {
    getKeys();
  }

  function handleDeleteKey(keys) {
    deleteApiKey(keys)
      .then((res) => {
        resetFilter();
        setSuccessData({
          title: "Success! Key deleted!",
        });
      })
      .catch((error) => {
        setErrorData({
          title: "Error on delete key",
          list: [error["response"]["data"]["detail"]],
        });
      });
  }

  function lastUsedMessage() {
    return (
      <div className="text-xs">
        <span>
          The last time this key was used.<br></br> Accurate to within the hour
          from the most recent usage.
        </span>
      </div>
    );
  }

  function getIdKeyHidden(apiKey: string) {
    const firstTwoChars = apiKey.slice(0, 2);
    const lastFourChars = apiKey.slice(-4);
    return firstTwoChars + "..." + lastFourChars;
  }

  return (
    <>
      {userData && (
        <div className="main-page-panel">
          <div className="m-auto flex h-full flex-row justify-center">
            <div className="basis-5/6">
              <div className="m-auto flex h-full flex-col space-y-8 p-8 ">
                <div className="flex items-center justify-between space-y-2">
                  <div>
                    <h2 className="text-2xl font-bold tracking-tight">
                      API keys
                    </h2>
                    <p className="text-muted-foreground">
                      Your secret API keys are listed below. Please note that we
                      do not display your secret API keys again after you
                      generate them.<br></br>
                      Do not share your API key with others, or expose it in the
                      browser or other client-side code.
                    </p>
                  </div>
                  <div className="flex items-center space-x-2"></div>
                </div>

                {keysList.current.length === 0 && !loadingKeys && (
                  <>
                    <div className="flex items-center justify-between">
                      <h2>There's no users registered :)</h2>
                    </div>
                  </>
                )}
                <>
                  {loadingKeys && (
                    <div>
                      <strong>Loading...</strong>
                    </div>
                  )}
                  <div
                    className={
                      "max-h-[15rem] overflow-scroll overflow-x-hidden rounded-md border-2 bg-muted custom-scroll" +
                      (loadingKeys ? " border-0" : "")
                    }
                  >
                    <Table className={"table-fixed bg-muted outline-1"}>
                      <TableHeader
                        className={
                          loadingKeys
                            ? "hidden"
                            : "table-fixed bg-muted outline-1"
                        }
                      >
                        <TableRow>
                          <TableHead className="h-10">Name</TableHead>
                          <TableHead className="h-10">Key</TableHead>
                          <TableHead className="h-10">Created</TableHead>
                          <TableHead className="flex h-10 items-center">
                            Last Used
                            <ShadTooltip side="top" content={lastUsedMessage()}>
                              <div>
                                <IconComponent
                                  name="Info"
                                  className="ml-1 h-3 w-3"
                                />
                              </div>
                            </ShadTooltip>
                          </TableHead>
                          <TableHead className="h-10 w-[100px]  text-right"></TableHead>
                        </TableRow>
                      </TableHeader>
                      {!loadingKeys && (
                        <TableBody>
                          {keysList.current.map((api_keys, index) => (
                            <TableRow key={index}>
                              <TableCell className="truncate py-2">
                                <ShadTooltip content={api_keys.name}>
                                  <span className="cursor-default">
                                    {api_keys.name}
                                  </span>
                                </ShadTooltip>
                              </TableCell>
                              <TableCell className="truncate py-2">
                                <span className="cursor-default">
                                  {getIdKeyHidden(api_keys.id)}
                                </span>
                              </TableCell>
                              <TableCell className="truncate py-2 ">
                                {moment(api_keys.create_at).format(
                                  "YYYY-MM-DD HH:mm"
                                )}
                              </TableCell>
                              <TableCell className="truncate py-2">
                                {moment(api_keys.last_used_at).format(
                                  "YYYY-MM-DD HH:mm"
                                )}
                              </TableCell>
                              <TableCell className="flex w-[100px] py-2 text-right">
                                <div className="flex">
                                  <ConfirmationModal
                                    title="Delete"
                                    titleHeader="Delete User"
                                    modalContentTitle="Attention!"
                                    modalContent="Are you sure you want to delete this key? This action cannot be undone."
                                    cancelText="Cancel"
                                    confirmationText="Delete"
                                    icon={"UserMinus2"}
                                    data={api_keys.id}
                                    index={index}
                                    onConfirm={(index, keys) => {
                                      handleDeleteKey(keys);
                                    }}
                                  >
                                    <ShadTooltip content="Delete" side="top">
                                      <IconComponent
                                        name="Trash2"
                                        className="ml-2 h-4 w-4 cursor-pointer"
                                      />
                                    </ShadTooltip>
                                  </ConfirmationModal>
                                </div>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      )}
                    </Table>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <SecretKeyModal
                        title="Create new secret key"
                        cancelText="Cancel"
                        confirmationText="Create secret key"
                        icon={"Key"}
                        data={userId}
                      >
                        <Button>
                          <IconComponent name="Plus" className="mr-1 h-5 w-5" />
                          Create new secret key
                        </Button>
                      </SecretKeyModal>
                    </div>
                  </div>
                </>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
