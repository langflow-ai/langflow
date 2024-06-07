from typing import Optional
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts.image import ImagePromptTemplate
from pydantic import BaseModel


class Message(BaseModel):
    # Helper class to deal with image data
    text: str
    sender: str
    sender_name: str
    files: list[str] = []
    session_id: str
    timestamp: str
    flow_id: Optional[str] = None

    def to_lc_message(
        self,
    ) -> BaseMessage:
        """
        Converts the Record to a BaseMessage.

        Returns:
            BaseMessage: The converted BaseMessage.
        """
        # The idea of this function is to be a helper to convert a Record to a BaseMessage
        # It will use the "sender" key to determine if the message is Human or AI
        # If the key is not present, it will default to AI
        # But first we check if all required keys are present in the data dictionary
        # they are: "text", "sender"
        if not self.text or not self.sender:
            raise ValueError("Missing required keys ('text', 'sender') in Message.")

        if self.sender == "User":
            if self.files:
                contents = [{"type": "text", "text": self.text}]
                for file_path in self.files:
                    image_template = ImagePromptTemplate()
                    image_prompt_value = image_template.invoke(input={"path": file_path})
                    contents.append({"type": "image_url", "image_url": image_prompt_value.image_url})
                human_message = HumanMessage(content=contents)
            else:
                human_message = HumanMessage(
                    content=[{"type": "text", "text": self.text}],
                )

            return human_message

        return AIMessage(content=self.text)
