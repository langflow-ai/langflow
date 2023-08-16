import { cloneDeep } from "lodash";
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
import {
  addUser,
  deleteUser,
  getUsersPage,
  updateUser,
} from "../../controllers/API";
import ConfirmationModal from "../../modals/ConfirmationModal";
import SecretKeyModal from "../../modals/SecretKeyModal";
import { UserInputType } from "../../types/components";

export default function ApiKeysPage() {
  const [inputValue, setInputValue] = useState("");

  const [size, setPageSize] = useState(10);
  const [index, setPageIndex] = useState(0);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const { userData } = useContext(AuthContext);
  const [totalRowsCount, setTotalRowsCount] = useState(0);

  const userList = useRef([]);

  useEffect(() => {
    setTimeout(() => {
      getUsers();
    }, 500);
  }, []);

  const [filterUserList, setFilterUserList] = useState(userList.current);

  function getUsers() {
    setLoadingUsers(true);
    getUsersPage(index, size)
      .then((users) => {
        setTotalRowsCount(users["total_count"]);
        userList.current = users["users"];
        setFilterUserList(users["users"]);
        setLoadingUsers(false);
      })
      .catch((error) => {
        setLoadingUsers(false);
      });
  }

  function handleChangePagination(pageIndex: number, pageSize: number) {
    setLoadingUsers(true);
    getUsersPage(pageIndex, pageSize)
      .then((users) => {
        setTotalRowsCount(users["total_count"]);
        userList.current = users["users"];
        setFilterUserList(users["users"]);
        setLoadingUsers(false);
      })
      .catch((error) => {
        setLoadingUsers(false);
      });
  }

  function resetFilter() {
    setPageIndex(0);
    setPageSize(10);
    getUsers();
  }

  function handleFilterUsers(input: string) {
    setInputValue(input);

    if (input === "") {
      setFilterUserList(userList.current);
    } else {
      const filteredList = userList.current.filter((user) =>
        user.username.toLowerCase().includes(input.toLowerCase())
      );
      setFilterUserList(filteredList);
    }
  }

  function handleDeleteUser(user) {
    deleteUser(user.id)
      .then((res) => {
        resetFilter();
        setSuccessData({
          title: "Success! User deleted!",
        });
      })
      .catch((error) => {
        setErrorData({
          title: "Error on delete user",
          list: [error["response"]["data"]["detail"]],
        });
      });
  }

  function handleEditUser(userId, user) {
    updateUser(userId, user)
      .then((res) => {
        resetFilter();
        setSuccessData({
          title: "Success! User edited!",
        });
      })
      .catch((error) => {
        setErrorData({
          title: "Error on edit user",
          list: [error["response"]["data"]["detail"]],
        });
      });
  }

  function handleDisableUser(check, userId, user) {
    const userEdit = cloneDeep(user);
    userEdit.is_active = !check;

    updateUser(userId, userEdit)
      .then((res) => {
        console.log(res);

        resetFilter();
        setSuccessData({
          title: "Success! User edited!",
        });
      })
      .catch((error) => {
        setErrorData({
          title: "Error on edit user",
          list: [error["response"]["data"]["detail"]],
        });
      });
  }

  function handleSuperUserEdit(check, userId, user) {
    const userEdit = cloneDeep(user);
    userEdit.is_superuser = !check;
    updateUser(userId, userEdit)
      .then((res) => {
        resetFilter();
        setSuccessData({
          title: "Success! User edited!",
        });
      })
      .catch((error) => {
        setErrorData({
          title: "Error on edit user",
          list: [error["response"]["data"]["detail"]],
        });
      });
  }

  function handleNewUser(user: UserInputType) {
    addUser(user)
      .then((res) => {
        resetFilter();
        setSuccessData({
          title: "Success! New user added!",
        });
      })
      .catch((error) => {
        setErrorData({
          title: "Error on add new user",
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

                {userList.current.length === 0 && !loadingUsers && (
                  <>
                    <div className="flex items-center justify-between">
                      <h2>There's no users registered :)</h2>
                    </div>
                  </>
                )}
                <>
                  {loadingUsers && (
                    <div>
                      <strong>Loading...</strong>
                    </div>
                  )}
                  <div
                    className={
                      "max-h-[15rem] min-h-[15rem] overflow-scroll overflow-x-hidden rounded-md border-2 bg-muted custom-scroll" +
                      (loadingUsers ? " border-0" : "")
                    }
                  >
                    <Table className={"table-fixed bg-muted outline-1"}>
                      <TableHeader
                        className={
                          loadingUsers
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
                      {!loadingUsers && (
                        <TableBody>
                          {filterUserList.map((user, index) => (
                            <TableRow key={index}>
                              <TableCell className="truncate py-2">
                                <ShadTooltip content={user.id}>
                                  <span className="cursor-default">
                                    {user.id}
                                  </span>
                                </ShadTooltip>
                              </TableCell>
                              <TableCell className="truncate py-2">
                                <ShadTooltip content={user.username}>
                                  <span className="cursor-default">
                                    {user.username}
                                  </span>
                                </ShadTooltip>
                              </TableCell>
                              <TableCell className="truncate py-2 ">
                                {
                                  new Date(user.create_at)
                                    .toISOString()
                                    .split("T")[0]
                                }
                              </TableCell>
                              <TableCell className="truncate py-2">
                                {
                                  new Date(user.updated_at)
                                    .toISOString()
                                    .split("T")[0]
                                }
                              </TableCell>
                              <TableCell className="flex w-[100px] py-2 text-right">
                                <div className="flex">
                                  <ConfirmationModal
                                    title="Delete"
                                    titleHeader="Delete User"
                                    modalContentTitle="Attention!"
                                    modalContent="Are you sure you want to delete this user? This action cannot be undone."
                                    cancelText="Cancel"
                                    confirmationText="Delete"
                                    icon={"UserMinus2"}
                                    data={user}
                                    index={index}
                                    onConfirm={(index, user) => {
                                      handleDeleteUser(user);
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
                        onConfirm={(index, user) => {
                          handleNewUser(user);
                        }}
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
