import _ from "lodash";
import { Pencil, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import PaginatorComponent from "../../components/PaginatorComponent";
import ShadTooltip from "../../components/ShadTooltipComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import ConfirmationModal from "../../modals/ConfirmationModal";
import UserManagementModal from "../../modals/UserManagementModal";
import IconComponent from "../../components/genericIconComponent";

export default function AdminPage() {
  const [inputValue, setInputValue] = useState("");

  const [size, setPageSize] = useState(10);
  const [index, setPageIndex] = useState(1);

  const userList = useRef([
    {
      user: generateRandomString(50),
      email: generateRandomString(50) + "@example.com",
      password: generateRandomString(50),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
    {
      user: generateRandomString(8),
      email: generateRandomString(10) + "@example.com",
      password: generateRandomString(12),
      register_date: generateRandomDate(),
    },
  ]);

  const [filterUserList, setFilterUserList] = useState(userList.current);

  function generateRandomString(length) {
    const characters =
      "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let result = "";
    for (let i = 0; i < length; i++) {
      const randomIndex = Math.floor(Math.random() * characters.length);
      result += characters.charAt(randomIndex);
    }
    return result;
  }

  function generateRandomDate() {
    const start = new Date(2010, 0, 1);
    const end = new Date();
    const randomTimestamp =
      start.getTime() + Math.random() * (end.getTime() - start.getTime());
    const randomDate = new Date(randomTimestamp);

    const options = { year: "numeric", month: "short", day: "numeric" };
    return randomDate.toLocaleDateString("en-US");
  }

  const [editUser, setEditUser] = useState(-1);
  const [editedUser, setEditedUser] = useState("");
  const [modalEditOpen, setModalEditOpen] = useState(false);
  const [modalDeleteOpen, setModalDeleteOpen] = useState(false);

  useEffect(() => {
    resetFilter();
  }, []);

  const handleInputChange = (event, index) => {
    const user = _.cloneDeepWith(userList.current);
    user[index].password = event.target.value;
    userList.current = user;

    const userFilter = _.cloneDeepWith(filterUserList);
    userFilter[index].password = event.target.value;
    setFilterUserList(userFilter);

    setEditedUser(event.target.value);
  };

  function handleChangePagination(pageIndex: number, pageSize: number) {
    setPageIndex(pageIndex);
    setPageSize(pageSize);

    const startIndex = (pageIndex - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const newList = userList.current.slice(startIndex, endIndex);

    setFilterUserList(newList);
  }

  function resetFilter() {
    setFilterUserList(userList.current);
    setPageIndex(1);
    setPageSize(10);

    const startIndex = (index - 1) * size;
    const endIndex = index + size - 1;
    const newList = userList.current.slice(startIndex, endIndex);

    console.log(userList.current);

    setFilterUserList(newList);
  }

  function handleFilterUsers(input: string) {
    setInputValue(input);

    if (input === "") {
      resetFilter();
    } else {
      const filteredList = userList.current.filter(
        (user) =>
          user.user.toLowerCase().includes(input.toLowerCase()) ||
          user.email.toLowerCase().includes(input.toLowerCase())
      );
      setFilterUserList(filteredList);
    }
  }

  function handleDeleteUser(index) {
    const user = _.cloneDeepWith(userList.current);
    user.splice(index, 1);
    userList.current = user;

    const userFilter = _.cloneDeepWith(filterUserList);
    userFilter.splice(index, 1);
    setFilterUserList(userFilter);

    resetFilter();
  }

  function handleEditUser(index, user) {
    const newUser = _.cloneDeepWith(userList.current);
    newUser[index].password = user.password;
    newUser[index].user = user.username;
    userList.current = newUser;
    resetFilter();
  }

  function handleNewUser(user) {
    const newUser = {
      user: user.username,
      email: generateRandomString(50) + "@example.com",
      password: user.password,
      register_date: generateRandomDate(),
    };

    userList.current.unshift(newUser);
    console.log(userList.current);

    resetFilter();
  }

  return (
    <>
      <div className="grid grid-cols-6 gap-4">
        <div className="col-span-4 col-start-2">
          <div className="m-auto h-full flex-1 flex-col space-y-8 p-8 md:flex">
            <div className="flex items-center justify-between space-y-2">
              <div>
                <h2 className="text-2xl font-bold tracking-tight">
                  Welcome back!
                </h2>
                <p className="text-muted-foreground">
                  Here&apos;s a list of all users!
                </p>
              </div>
              <div className="flex items-center space-x-2"></div>
            </div>

            {userList.current.length === 0 && (
              <>
                <div className="flex items-center justify-between">
                  <h2>There's no users left :)</h2>
                </div>
              </>
            )}
            {userList.current.length > 0 && (
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
                          resetFilter();
                          setInputValue("");
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
                <div
                  className="overflow-scroll overflow-x-hidden rounded-md border-2 bg-muted 
            custom-scroll min-[320px]:h-[15rem] md:h-[20rem] xl:h-[25rem] 2xl:h-[30rem]"
                >
                  <Table className="table-fixed bg-muted outline-1 ">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="h-10">User</TableHead>
                        <TableHead className="h-10">Password</TableHead>
                        <TableHead className="h-10 w-[100px]  text-right"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filterUserList.map((user, index) => (
                        <TableRow key={user.user}>
                          <TableCell className="truncate py-2 font-medium">
                            {user.user}
                          </TableCell>
                          <TableCell className="truncate py-2">
                            {user.password}
                          </TableCell>
                          <TableCell className="flex w-[100px] py-2 text-right">
                            <div className="flex">
                              <UserManagementModal
                                title="Edit"
                                titleHeader={`${user.user}`}
                                cancelText="Cancel"
                                confirmationText="Edit"
                                icon={"UserPlus2"}
                                data={user}
                                index={index}
                                onConfirm={(index, user) => {
                                  handleEditUser(index, user);
                                }}
                              >
                                <ShadTooltip content="Edit" side="top">
                                  <IconComponent name="Pencil"
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
                                  handleDeleteUser(index);
                                }}
                              >
                                <ShadTooltip content="Delete" side="top">
                                  <IconComponent name="Trash2"
                                    className="ml-2 h-4 w-4 cursor-pointer"
                                  />
                                </ShadTooltip>
                              </ConfirmationModal>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                <PaginatorComponent
                  pageIndex={index}
                  pageSize={size}
                  totalRowsCount={filterUserList.length}
                  paginate={(pageIndex, pageSize) => {
                    handleChangePagination(pageSize, pageIndex);
                  }}
                ></PaginatorComponent>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
