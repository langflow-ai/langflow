import { lazy } from "react";
import { IS_CLERK_AUTH } from "../constants/clerk";

import OriginalLoginPage from "../pages/LoginPage";
import ClerkLoginPage from "../pages/ClerkLoginPage";
import OriginalSignUp from "../pages/SignUpPage";
import ClerkSignUpPage from "../pages/ClerkSignUpPage";

const OriginalLoginAdminPage = lazy(() => import("../pages/AdminPage/LoginPage"));

export const LoginPage = IS_CLERK_AUTH ? ClerkLoginPage : OriginalLoginPage;
export const SignUp = IS_CLERK_AUTH ? ClerkSignUpPage : OriginalSignUp;
export const LoginAdminPage = IS_CLERK_AUTH ? ClerkLoginPage : OriginalLoginAdminPage;
