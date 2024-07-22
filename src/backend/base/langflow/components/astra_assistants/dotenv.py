import io

from dotenv import load_dotenv

from langflow.custom import CustomComponent


class Dotenv(CustomComponent):
    display_name = "Dotenv"
    description = "Load .env file into env vars"

    def build_config(self):
        return {
            "dotenv_file_content": {
                "display_name": "Dotenv file content",
                "advanced": False,
                "info": (
                    "Paste the content of your .env file directly\n\n"
                    "Since contents are sensitive, using a Global variable set as 'password' is recommended"
                ),
            },
        }

    def build(self, dotenv_file_content: str) -> str:
        try:
            fake_file = io.StringIO(dotenv_file_content)
            result = load_dotenv(stream=fake_file, override=True)
            return "Loaded .env" if result else "No variables found in .env"
        except Exception as e:
            raise e
