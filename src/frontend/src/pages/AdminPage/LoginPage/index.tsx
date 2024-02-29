import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { SIGNIN_ERROR_ALERT } from "../../../constants/alerts_constants";
import { CONTROL_LOGIN_STATE } from "../../../constants/constants";
import { AuthContext } from "../../../contexts/authContext";
import { onLogin } from "../../../controllers/API";
import useAlertStore from "../../../stores/alertStore";
import { LoginType } from "../../../types/api";
import {
  inputHandlerEventType,
  loginInputStateType,
} from "../../../types/components";

export default function LoginAdminPage() {
  const navigate = useNavigate();

  const [inputState, setInputState] =
    useState<loginInputStateType>(CONTROL_LOGIN_STATE);
  const { login, isAuthenticated, setUserData } = useContext(AuthContext);

  const { password, username } = inputState;
  const setErrorData = useAlertStore((state) => state.setErrorData);
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
        login(user.access_token);
        navigate("/admin/");
      })
      .catch((error) => {
        setErrorData({
          title: SIGNIN_ERROR_ALERT,
          list: [error["response"]["data"]["detail"]],
        });
      });
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
