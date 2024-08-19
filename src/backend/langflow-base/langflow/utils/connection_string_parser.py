from urllib.parse import quote


def transform_connection_string(connection_string):
    db_url_name = connection_string.split("@")[-1]
    password_url = connection_string.split(":")[-1]
    password_string = password_url.replace(f"@{db_url_name}", "")
    encoded_password = quote(password_string)
    protocol_user = connection_string.split(":")[:-1]
    transformed_connection_string = f'{":".join(protocol_user)}:{encoded_password}@{db_url_name}'
    return transformed_connection_string
