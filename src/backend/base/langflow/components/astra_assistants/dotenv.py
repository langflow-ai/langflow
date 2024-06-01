import io
from dotenv import load_dotenv
from langflow.custom import CustomComponent


class Dotenv(CustomComponent):
    display_name = "Dotenv"
    description = "Load .env file into env vars"

    def build(self, dotenv_file_content: str) -> str:
        try:
            fake_file = io.StringIO(dotenv_file_content)
            result = load_dotenv(stream=fake_file, override=True)
            return result
        except Exception as e:
            raise e
