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
import Header from "../../components/headerComponent";
import {
  API_PAGE_PARAGRAPH_1,
  API_PAGE_PARAGRAPH_2,
  API_PAGE_USER_KEYS,
  LAST_USED_SPAN_1,
  LAST_USED_SPAN_2,
} from "../../constants/constants";
import { ApiKey } from "../../types/components";

export default function ApiKeysPage() {
  const [loadingKeys, setLoadingKeys] = useState(true);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const { userData } = useContext(AuthContext);
  const [userId, setUserId] = useState("");
  const keysList = useRef([]);

  useEffect(() => {
    getKeys();
  }, [userData]);

  function getKeys() {
    setLoadingKeys(true);
    if (userData) {
      getApiKey()
        .then((keys: [ApiKey]) => {
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
          {LAST_USED_SPAN_1}
          <br></br> {LAST_USED_SPAN_2}
        </span>
      </div>
    );
  }

  return (
    <>
      <Header></Header>
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
                      {API_PAGE_PARAGRAPH_1}
                      <br />
                      {API_PAGE_PARAGRAPH_2}
                    </p>
                  </div>
                  <div className="flex items-center space-x-2"></div>
                </div>

                {keysList.current &&
                  keysList.current.length === 0 &&
                  !loadingKeys && (
                    <>
                      <div className="flex items-center justify-between">
                        <h2>{API_PAGE_USER_KEYS}</h2>
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
                    {keysList.current &&
                      keysList.current.length > 0 &&
                      !loadingKeys && (
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
                                <ShadTooltip
                                  side="top"
                                  content={lastUsedMessage()}
                                >
                                  <div>
                                    <IconComponent
                                      name="Info"
                                      className="ml-1 h-3 w-3"
                                    />
                                  </div>
                                </ShadTooltip>
                              </TableHead>
                              <TableHead className="h-10">Total Uses</TableHead>
                              <TableHead className="h-10 w-[100px]  text-right"></TableHead>
                            </TableRow>
                          </TableHeader>
                          {!loadingKeys && (
                            <TableBody>
                              {keysList.current.map(
                                (api_keys: ApiKey, index: number) => (
                                  <TableRow key={index}>
                                    <TableCell className="truncate py-2">
                                      <ShadTooltip content={api_keys.name}>
                                        <span className="cursor-default">
                                          {api_keys.name ? api_keys.name : "-"}
                                        </span>
                                      </ShadTooltip>
                                    </TableCell>
                                    <TableCell className="truncate py-2">
                                      <span className="cursor-default">
                                        {api_keys.api_key}
                                      </span>
                                    </TableCell>
                                    <TableCell className="truncate py-2 ">
                                      <ShadTooltip
                                        side="top"
                                        content={moment(
                                          api_keys.created_at
                                        ).format("YYYY-MM-DD HH:mm")}
                                      >
                                        <div>
                                          {moment(api_keys.created_at).format(
                                            "YYYY-MM-DD HH:mm"
                                          )}
                                        </div>
                                      </ShadTooltip>
                                    </TableCell>
                                    <TableCell className="truncate py-2">
                                      <ShadTooltip
                                        side="top"
                                        content={
                                          moment(api_keys.last_used_at).format(
                                            "YYYY-MM-DD HH:mm"
                                          ) === "Invalid date"
                                            ? "Never"
                                            : moment(
                                                api_keys.last_used_at
                                              ).format("YYYY-MM-DD HH:mm")
                                        }
                                      >
                                        <div>
                                          {moment(api_keys.last_used_at).format(
                                            "YYYY-MM-DD HH:mm"
                                          ) === "Invalid date"
                                            ? "Never"
                                            : moment(
                                                api_keys.last_used_at
                                              ).format("YYYY-MM-DD HH:mm")}
                                        </div>
                                      </ShadTooltip>
                                    </TableCell>
                                    <TableCell className="truncate py-2">
                                      {api_keys.total_uses}
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
                                          <ShadTooltip
                                            content="Delete"
                                            side="top"
                                          >
                                            <IconComponent
                                              name="Trash2"
                                              className="ml-2 h-4 w-4 cursor-pointer"
                                            />
                                          </ShadTooltip>
                                        </ConfirmationModal>
                                      </div>
                                    </TableCell>
                                  </TableRow>
                                )
                              )}
                            </TableBody>
                          )}
                        </Table>
                      )}
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <SecretKeyModal
                        title="Create new secret key"
                        cancelText="Cancel"
                        confirmationText="Create secret key"
                        icon={"Key"}
                        data={userId}
                        onCloseModal={getKeys}
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
