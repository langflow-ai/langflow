from pydantic import BaseModel


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


fake_users_db = {
    "gustavo": {
        "username": "gustavo",
        "full_name": "Gustavo Schaedler",
        "email": "gustavopoa@gmail.com",
        "hashed_password": "$2b$12$f4R8IHUaVxVchhpWrwhckeJXnPalW1vUbJzcvb1KeovJcuMwE861K", #secret
        "disabled": False,
    },
    "gustavo_disabled": {
        "username": "gustavo_disabled",
        "full_name": "Gustavo Disabled",
        "email": "gustavo_disabled@gmail.com",
        "hashed_password": "$2b$12$f4R8IHUaVxVchhpWrwhckeJXnPalW1vUbJzcvb1KeovJcuMwE861K", #secret
        "disabled": True,
    }
}


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
