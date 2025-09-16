from starlette.requests import Request
from starlette.responses import JSONResponse


async def auth_init(request: Request, auth_service):
    """Initialize OAuth flow for authentication or data source connection."""
    try:
        data = await request.json()
        connector_type = data.get("connector_type")
        purpose = data.get("purpose", "data_source")
        connection_name = data.get("name", f"{connector_type}_{purpose}")
        redirect_uri = data.get("redirect_uri")

        user = getattr(request.state, "user", None)
        user_id = user.user_id if user else None

        result = await auth_service.init_oauth(
            connector_type, purpose, connection_name, redirect_uri, user_id
        )
        return JSONResponse(result)

    except ValueError as e:
        import traceback

        traceback.print_exc()
        return JSONResponse(
            {"error": f"Failed to initialize OAuth: {e!s}"}, status_code=500
        )


async def auth_callback(request: Request, auth_service):
    """Handle OAuth callback - exchange authorization code for tokens."""
    try:
        data = await request.json()
        connection_id = data.get("connection_id")
        authorization_code = data.get("authorization_code")
        state = data.get("state")

        result = await auth_service.handle_oauth_callback(
            connection_id, authorization_code, state, request
        )

        # If this is app auth, set JWT cookie
        if result.get("purpose") == "app_auth" and result.get("jwt_token"):
            response = JSONResponse(
                {k: v for k, v in result.items() if k != "jwt_token"}
            )
            response.set_cookie(
                key="auth_token",
                value=result["jwt_token"],
                httponly=True,
                secure=False,
                samesite="lax",
                max_age=7 * 24 * 60 * 60,  # 7 days
            )
            return response
        return JSONResponse(result)

    except ValueError as e:
        import traceback

        traceback.print_exc()
        return JSONResponse({"error": f"Callback failed: {e!s}"}, status_code=500)


async def auth_me(request: Request, auth_service):
    """Get current user information."""
    result = await auth_service.get_user_info(request)
    return JSONResponse(result)


async def auth_logout():
    """Logout user by clearing auth cookie."""
    response = JSONResponse(
        {"status": "logged_out", "message": "Successfully logged out"}
    )

    # Clear the auth cookie
    response.delete_cookie(
        key="auth_token", httponly=True, secure=False, samesite="lax"
    )

    return response
