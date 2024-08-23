from urllib.parse import quote


def transform_connection_string(connection_string):
    auth_part, db_url_name = connection_string.rsplit("@", 1)
    protocol_user, password_string = auth_part.rsplit(":", 1)
    encoded_password = quote(password_string)
    transformed_connection_string = f"{protocol_user}:{encoded_password}@{db_url_name}"
    return transformed_connection_string
