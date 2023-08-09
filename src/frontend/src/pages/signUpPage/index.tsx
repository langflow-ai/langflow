import _ from "lodash";
import { FaApple, FaGithub } from "react-icons/fa";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { GoogleIcon } from "../../icons/Google";
import { useContext, useState } from "react";
import { CONTROL_INPUT_STATE } from "../../constants/constants";
import { inputHandlerEventType, inputStateType } from "../../types/components";
import { alertContext } from "../../contexts/alertContext";
import { Link } from "react-router-dom";
import InputComponent from "../../components/inputComponent";

export default function SignUp(): JSX.Element {
  const [inputState, setInputState] = useState<inputStateType>(CONTROL_INPUT_STATE);
  let errClasses = {
	email: false,
	password: false,
	cnfPassword: false,
	username: false,
  };

  const {
	setErrorData,
	errorOpen,
  } = useContext(alertContext);

  const { email, password, cnfPassword, username } = inputState;

  function handleInput({ target: { name, value } }: inputHandlerEventType): void {
	setInputState((prev) => ({ ...prev, [name]: value }));
  };

  function handleSignUpPass() {
  	if (password !== cnfPassword) {
    	const errorDat = {
      	title: "Passwords are not equal",
    	};
    	return setErrorData(errorDat);
  	}
  	let err = [];
  	Object.keys(inputState)
  	.forEach((key) => {
    	if (inputState[key] === '') {
      	err.push(key);
      	errClasses[key] = true;
    	}
  	});
  	setErrorData({
    	title: "Mandatory fields are empty",
    	list: err,
  	});
	}
  return (
  	<div className="flex h-full w-full flex-col items-center justify-center bg-muted">
    	<div className="flex w-72 flex-col items-center justify-center gap-2">
      	<span className="mb-4 text-5xl">⛓️</span>
      	<span className="mb-6 text-2xl font-semibold text-primary">
        	Sign up to LangFlow
      	</span>
      	<div className="flex w-full items-center justify-center gap-2">
        	<Button variant="primary" className="w-full py-6">
          	<FaApple className="h-6 w-6" />
        	</Button>
        	<Button variant="primary" className="w-full py-6">
          	<FaGithub className="h-6 w-6" />
        	</Button>
        	<Button variant="primary" className="w-full py-6">
          	<div className="h-6 w-6">
            	<GoogleIcon />
          	</div>
        	</Button>
      	</div>
      	<span className="text-sm text-muted-foreground">or</span>
      	<Input
        	className={errClasses.email ? "border-destructive" : "" + " bg-background"}
        	placeholder="Email address"
        	name="email"
        	value={email}
        	onChange={handleInput}
        	type="text"
      	/>
      	<InputComponent
        	value={password}
        	onChange={(value) => handleInput({ target: { name: 'password', value } })}
        	password={true}
        	placeholder="Password"
      	/>
      	<InputComponent
        	value={cnfPassword}
        	onChange={(value) => handleInput({ target: { name: 'cnfPassword', value } })}
        	password={true}
        	placeholder="Confirm your password"
      	/>
      	<Input
        	className="bg-background"
        	placeholder="Username"
        	name="username"
        	value={username}
        	onChange={handleInput}
        	type="text"
      	/>
      	<Button
        	variant="default"
        	className="w-full"
        	onClick={() => {
          	handleSignUpPass();
        	}}
      	>
        	Sign up
      	</Button>
      	<Link to="/login" className="mt-6 w-full">
        	<Button variant="outline" className="mt-6 w-full">
          	Already have an account?&nbsp;<b>Sign in</b>
        	</Button>
      	</Link>
    	</div>
  	</div>
  );
}
