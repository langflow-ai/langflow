def initialize_vertexai(class_object, params):
    if credentials_path := params.get("credentials"):
        from google.oauth2 import service_account  # type: ignore

        credentials_object = service_account.Credentials.from_service_account_file(
            filename=credentials_path
        )
        params["credentials"] = credentials_object
    return class_object(**params)
