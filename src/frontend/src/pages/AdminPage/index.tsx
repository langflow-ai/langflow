import { cloneDeep } from "lodash";
import { X } from "lucide-react";
import { useContext, useEffect, useRef, useState } from "react";
import PaginatorComponent from "../../components/PaginatorComponent";
import ShadTooltip from "../../components/ShadTooltipComponent";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { Input } from "../../components/ui/input";
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
import UserManagementModal from "../../modals/UserManagementModal";
import { Users } from "../../types/api";
import { UserInputType } from "../../types/components";

export default function AdminPage() {
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
      const filteredList = userList.current.filter((user: Users) =>
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

  return (
    <>
      <div className="flex flex-col">
        <Header />
        {userData && (
          <div className="main-page-panel">
            <div className="m-auto flex h-full flex-row justify-center">
              <div className="basis-5/6">
                <div className="m-auto flex h-full flex-col space-y-8 p-8 ">
                  <div className="flex items-center justify-between space-y-2">
                    <div>
                      <h2 className="text-2xl font-bold tracking-tight">
                        Welcome back!
                      </h2>
                      <p className="text-muted-foreground">
                        Navigate through this section to efficiently oversee all
                        application users. From here, you can seamlessly manage
                        user accounts.
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
                    <div className="flex items-center justify-between">
                      <div className="flex flex-1 items-center space-x-2">
                        <Input
                          value={inputValue}
                          placeholder="Filter users..."
                          className="h-8 w-[150px] lg:w-[250px]"
                          onChange={(e) => handleFilterUsers(e.target.value)}
                        />
                        {inputValue.length > 0 && (
                          <Button
                            onClick={() => {
                              setInputValue("");
                              setFilterUserList(userList.current);
                            }}
                            variant="ghost"
                            className="h-8 px-2 lg:px-3"
                          >
                            Reset
                            <X className="ml-2 h-4 w-4" />
                          </Button>
                        )}
                      </div>
                      <div>
                        <UserManagementModal
                          title="New User"
                          titleHeader={"Add a new user"}
                          cancelText="Cancel"
                          confirmationText="Save"
                          icon={"UserPlus2"}
                          onConfirm={(index, user) => {
                            handleNewUser(user);
                          }}
                        >
                          <Button>New User</Button>
                        </UserManagementModal>
                      </div>
                    </div>
                    {loadingUsers && (
                      <div>
                        <strong>Loading...</strong>
                      </div>
                    )}
                    <div
                      className={
                        "max-h-[26rem] min-h-[26rem] overflow-scroll overflow-x-hidden rounded-md border-2 bg-muted custom-scroll" +
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
                            <TableHead className="h-10">Id</TableHead>
                            <TableHead className="h-10">Username</TableHead>
                            <TableHead className="h-10">Active</TableHead>
                            <TableHead className="h-10">Superuser</TableHead>
                            <TableHead className="h-10">Created At</TableHead>
                            <TableHead className="h-10">Updated At</TableHead>
                            <TableHead className="h-10 w-[100px]  text-right"></TableHead>
                          </TableRow>
                        </TableHeader>
                        {!loadingUsers && (
                          <TableBody>
                            {filterUserList.map(
                              (user: UserInputType, index) => (
                                <TableRow key={index}>
                                  <TableCell className="truncate py-2 font-medium">
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
                                  <TableCell className="relative left-5 truncate py-2 text-align-last-left">
                                    <ConfirmationModal
                                      title="Edit"
                                      titleHeader={`${user.username}`}
                                      modalContentTitle="Attention!"
                                      modalContent="Are you completely confident about the changes you are making to this user?"
                                      cancelText="Cancel"
                                      confirmationText="Confirm"
                                      icon={"UserCog2"}
                                      data={user}
                                      index={index}
                                      onConfirm={(index, user) => {
                                        handleDisableUser(
                                          user.is_active,
                                          user.id,
                                          user
                                        );
                                      }}
                                    >
                                      <Checkbox
                                        id="is_active"
                                        checked={user.is_active}
                                      />
                                    </ConfirmationModal>
                                  </TableCell>
                                  <TableCell className="relative left-5 truncate py-2 text-align-last-left">
                                    <ConfirmationModal
                                      title="Edit"
                                      titleHeader={`${user.username}`}
                                      modalContentTitle="Attention!"
                                      modalContent="Are you completely confident about the changes you are making to this user?"
                                      cancelText="Cancel"
                                      confirmationText="Confirm"
                                      icon={"UserCog2"}
                                      data={user}
                                      index={index}
                                      onConfirm={(index, user) => {
                                        handleSuperUserEdit(
                                          user.is_superuser,
                                          user.id,
                                          user
                                        );
                                      }}
                                    >
                                      <Checkbox
                                        id="is_superuser"
                                        checked={user.is_superuser}
                                      />
                                    </ConfirmationModal>
                                  </TableCell>
                                  <TableCell className="truncate py-2 ">
                                    {
                                      new Date(user.create_at!)
                                        .toISOString()
                                        .split("T")[0]
                                    }
                                  </TableCell>
                                  <TableCell className="truncate py-2">
                                    {
                                      new Date(user.updated_at!)
                                        .toISOString()
                                        .split("T")[0]
                                    }
                                  </TableCell>
                                  <TableCell className="flex w-[100px] py-2 text-right">
                                    <div className="flex">
                                      <UserManagementModal
                                        title="Edit"
                                        titleHeader={`${user.id}`}
                                        cancelText="Cancel"
                                        confirmationText="Save"
                                        icon={"UserPlus2"}
                                        data={user}
                                        index={index}
                                        onConfirm={(index, editUser) => {
                                          handleEditUser(user.id, editUser);
                                        }}
                                      >
                                        <ShadTooltip content="Edit" side="top">
                                          <IconComponent
                                            name="Pencil"
                                            className="h-4 w-4 cursor-pointer"
                                          />
                                        </ShadTooltip>
                                      </UserManagementModal>

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
                    </div>

                    <PaginatorComponent
                      pageIndex={index}
                      pageSize={size}
                      totalRowsCount={totalRowsCount}
                      paginate={(pageIndex, pageSize) => {
                        handleChangePagination(pageSize, pageIndex);
                      }}
                    ></PaginatorComponent>
                  </>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
