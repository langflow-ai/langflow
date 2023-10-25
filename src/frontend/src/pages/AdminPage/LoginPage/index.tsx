import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { CONTROL_LOGIN_STATE } from "../../../constants/constants";
import { alertContext } from "../../../contexts/alertContext";
import { AuthContext } from "../../../contexts/authContext";
import { getLoggedUser, onLogin } from "../../../controllers/API";
import { LoginType } from "../../../types/api";
import {
  inputHandlerEventType,
  loginInputStateType,
} from "../../../types/components";

export default function LoginAdminPage() {
  const navigate = useNavigate();

  const [inputState, setInputState] =
    useState<loginInputStateType>(CONTROL_LOGIN_STATE);
  const { login, getAuthentication, setUserData } = useContext(AuthContext);

  const { password, username } = inputState;
  const { setErrorData } = useContext(alertContext);

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  function signIn() {
    const user: LoginType = {
      username: username,
      password: password,
    };
    onLogin(user)
      .then((user) => {
        login(user.access_token, user.refresh_token);
        getUser();
        navigate("/admin/");
      })
      .catch((error) => {
        setErrorData({
          title: "Error signing in",
          list: [error["response"]["data"]["detail"]],
        });
      });
  }

  function getUser() {
    if (getAuthentication()) {
      setTimeout(() => {
        getLoggedUser()
          .then((user) => {
            setUserData(user);
          })
          .catch((error) => {
            console.log("login admin page", error);
          });
      }, 1000);
    }
  }

  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
      <div className="flex w-72 flex-col items-center justify-center gap-2">
        <span className="mb-4 text-5xl">⛓️</span>
        <span className="mb-6 text-2xl font-semibold text-primary">Admin</span>
        <Input
          onChange={({ target: { value } }) => {
            handleInput({ target: { name: "username", value } });
          }}
          className="bg-background"
          placeholder="Username"
        />
        <Input
          type="password"
          onChange={({ target: { value } }) => {
            handleInput({ target: { name: "password", value } });
          }}
          className="bg-background"
          placeholder="Password"
        />
        <Button
          onClick={() => {
            signIn();
          }}
          variant="default"
          className="w-full"
        >
          Login
        </Button>
      </div>
    </div>
  );
}
