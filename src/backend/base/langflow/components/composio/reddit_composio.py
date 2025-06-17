import json
from typing import Any

from composio import Action

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs import (
    BoolInput,
    IntInput,
    MessageTextInput,
)
from langflow.logging import logger


class ComposioRedditAPIComponent(ComposioBaseComponent):
    display_name: str = "Reddit"
    name = "RedditAPI"
    description: str = "Reddit API"
    icon = "Reddit"
    documentation: str = "https://docs.composio.dev"
    app_name = "reddit"

    _actions_data: dict = {
        "REDDIT_CREATE_REDDIT_POST": {
            "display_name": "Create Reddit Post",
            "action_fields": [
                "REDDIT_CREATE_REDDIT_POST_flair_id",
                "REDDIT_CREATE_REDDIT_POST_kind",
                "REDDIT_CREATE_REDDIT_POST_subreddit",
                "REDDIT_CREATE_REDDIT_POST_text",
                "REDDIT_CREATE_REDDIT_POST_title",
                "REDDIT_CREATE_REDDIT_POST_url",
            ],
            "get_result_field": True,
            "result_field": "items",
        },
        "REDDIT_DELETE_REDDIT_COMMENT": {
            "display_name": "Delete Reddit Comment",
            "action_fields": ["REDDIT_DELETE_REDDIT_COMMENT_id"],
            "get_result_field": False,
        },
        "REDDIT_DELETE_REDDIT_POST": {
            "display_name": "Delete Reddit Post",
            "action_fields": ["REDDIT_DELETE_REDDIT_POST_id"],
            "get_result_field": False,
        },
        "REDDIT_EDIT_REDDIT_COMMENT_OR_POST": {
            "display_name": "Edit Reddit Comment Or Post",
            "action_fields": [
                "REDDIT_EDIT_REDDIT_COMMENT_OR_POST_text",
                "REDDIT_EDIT_REDDIT_COMMENT_OR_POST_thing_id",
            ],
            "get_result_field": False,
        },
        "REDDIT_GET_USER_FLAIR": {
            "display_name": "Get User Flair",
            "action_fields": ["REDDIT_GET_USER_FLAIR_subreddit"],
            "get_result_field": True,
            "result_field": "flair_list",
        },
        "REDDIT_POST_REDDIT_COMMENT": {
            "display_name": "Post Reddit Comment",
            "action_fields": [
                "REDDIT_POST_REDDIT_COMMENT_text",
                "REDDIT_POST_REDDIT_COMMENT_thing_id",
            ],
            "get_result_field": False,
        },
        "REDDIT_RETRIEVE_POST_COMMENTS": {
            "display_name": "Retrieve Post Comments",
            "action_fields": ["REDDIT_RETRIEVE_POST_COMMENTS_article"],
            "get_result_field": True,
            "result_field": "comments",
        },
        "REDDIT_RETRIEVE_REDDIT_POST": {
            "display_name": "Retrieve Reddit Post",
            "action_fields": [
                "REDDIT_RETRIEVE_REDDIT_POST_size",
                "REDDIT_RETRIEVE_REDDIT_POST_subreddit",
            ],
            "get_result_field": True,
            "result_field": "posts_list",
        },
        "REDDIT_RETRIEVE_SPECIFIC_COMMENT": {
            "display_name": "Retrieve Specific Comment",
            "action_fields": ["REDDIT_RETRIEVE_SPECIFIC_COMMENT_id"],
            "get_result_field": True,
            "result_field": "things",
        },
        "REDDIT_SEARCH_ACROSS_SUBREDDITS": {
            "display_name": "Search Across Subreddits",
            "action_fields": [
                "REDDIT_SEARCH_ACROSS_SUBREDDITS_limit",
                "REDDIT_SEARCH_ACROSS_SUBREDDITS_restrict_sr",
                "REDDIT_SEARCH_ACROSS_SUBREDDITS_search_query",
                "REDDIT_SEARCH_ACROSS_SUBREDDITS_sort",
            ],
            "get_result_field": True,
            "result_field": "children",
        },
    }

    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}

    _bool_variables = {
        "REDDIT_SEARCH_ACROSS_SUBREDDITS_restrict_sr",
    }

    inputs = [
        *ComposioBaseComponent._base_inputs,
        MessageTextInput(
            name="REDDIT_CREATE_REDDIT_POST_flair_id",
            display_name="Flair ID",
            info="The ID of the flair to apply to the post. Use the 'REDDIT_GET_USER_FLAIR' action to find available flair IDs for the specified subreddit.",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_CREATE_REDDIT_POST_kind",
            display_name="Kind",
            info="The type of the post. Use 'self' for a text-based post or 'link' for a post that links to an external URL.",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_CREATE_REDDIT_POST_subreddit",
            display_name="Subreddit",
            info="The name of the subreddit (without the 'r/' prefix) where the post will be submitted.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_CREATE_REDDIT_POST_text",
            display_name="Text",
            info="The markdown-formatted text content for a 'self' post. Required if `kind` is 'self'.",
            show=False,
        ),
        MessageTextInput(
            name="REDDIT_CREATE_REDDIT_POST_title",
            display_name="Title",
            info="The title of the post. Must be 300 characters or less.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_CREATE_REDDIT_POST_url",
            display_name="Url",
            info="The URL for a 'link' post. Required if `kind` is 'link'.",
            show=False,
        ),
        MessageTextInput(
            name="REDDIT_DELETE_REDDIT_COMMENT_id",
            display_name="ID",
            info="The full 'thing ID' (fullname, e.g., 't1_c0s4w1c') of the comment to delete; typically starts with 't1_'.",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_DELETE_REDDIT_POST_id",
            display_name="ID",
            info="The full name (fullname) of the Reddit post to be deleted. This ID must start with 't3_' followed by the post's unique base36 identifier.",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_EDIT_REDDIT_COMMENT_OR_POST_text",
            display_name="Text",
            info="The new raw markdown text for the body of the comment or self-post.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_EDIT_REDDIT_COMMENT_OR_POST_thing_id",
            display_name="Thing ID",
            info="The full name (fullname) of the comment or self-post to edit. This is a combination of a prefix (e.g., 't1_' for comment, 't3_' for post) and the item's ID.",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_GET_USER_FLAIR_subreddit",
            display_name="Subreddit",
            info="Name of the subreddit (e.g., 'pics', 'gaming') for which to retrieve available link flairs.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_POST_REDDIT_COMMENT_text",
            display_name="Text",
            info="The raw Markdown text of the comment to be submitted.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_POST_REDDIT_COMMENT_thing_id",
            display_name="Thing ID",
            info="The ID of the parent post (link) or comment, prefixed with 't3_' for a post (e.g., 't3_10omtdx') or 't1_' for a comment (e.g., 't1_h2g9w8l').",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_RETRIEVE_POST_COMMENTS_article",
            display_name="Article",
            info="Base_36 ID of the Reddit post (e.g., 'q5u7q5'), typically found in the post's URL and not including the 't3_' prefix.",  # noqa: E501
            show=False,
            required=True,
        ),
        IntInput(
            name="REDDIT_RETRIEVE_REDDIT_POST_size",
            display_name="Size",
            info="The maximum number of posts to return. Default is 5. Set to 0 to retrieve all available posts (or the maximum allowed by the Reddit API for a single request, typically up to 100 for this type of listing).",  # noqa: E501
            show=False,
            value=5,
        ),
        MessageTextInput(
            name="REDDIT_RETRIEVE_REDDIT_POST_subreddit",
            display_name="Subreddit",
            info="The name of the subreddit from which to retrieve posts (e.g., 'popular', 'pics'). Do not include 'r/'.",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_RETRIEVE_SPECIFIC_COMMENT_id",
            display_name="ID",
            info="Fullname of the comment or post to retrieve (e.g., 't1_c123456', 't3_x56789').",
            show=False,
            required=True,
        ),
        IntInput(
            name="REDDIT_SEARCH_ACROSS_SUBREDDITS_limit",
            display_name="Limit",
            info="The maximum number of search results to return. Default is 5. Maximum allowed value is 100.",
            show=False,
            value=5,
        ),
        BoolInput(
            name="REDDIT_SEARCH_ACROSS_SUBREDDITS_restrict_sr",
            display_name="Restrict SR",
            info="If True (default), confines the search to posts and comments within subreddits. If False, the search scope is broader and may include matching subreddit names or other Reddit entities.",  # noqa: E501
            show=False,
            value=True,
        ),
        MessageTextInput(
            name="REDDIT_SEARCH_ACROSS_SUBREDDITS_search_query",
            display_name="Search Query",
            info="The search query string used to find content across subreddits.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="REDDIT_SEARCH_ACROSS_SUBREDDITS_sort",
            display_name="Sort",
            info="The criterion for sorting search results. 'relevance' (default) sorts by relevance to the query. 'new' sorts by newest first. 'top' sorts by highest score (typically all-time). 'comments' sorts by the number of comments.",  # noqa: E501
            show=False,
            value="relevance",
        ),
    ]

    def _find_key_recursively(self, data, key):
        """Recursively search for a key in nested dicts/lists and return its value if found."""
        if isinstance(data, dict):
            if key in data:
                return data[key]
            for v in data.values():
                found = self._find_key_recursively(v, key)
                if found is not None:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = self._find_key_recursively(item, key)
                if found is not None:
                    return found
        return None

    def _convert_pandas_to_python(self, obj):
        """Recursively convert pandas objects to plain Python objects."""
        if hasattr(obj, "to_dict"):  # pandas DataFrame
            return obj.to_dict("records")
        if hasattr(obj, "tolist"):  # pandas Series
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: self._convert_pandas_to_python(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._convert_pandas_to_python(item) for item in obj]
        return obj

    def execute_action(self):
        """Execute action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            self._build_action_maps()
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else self.action
            action_key = self._display_to_key_map.get(display_name)
            if not action_key:
                msg = f"Invalid action: {display_name}"
                raise ValueError(msg)

            enum_name = getattr(Action, action_key)
            params = {}
            if action_key in self._actions_data:
                for field in self._actions_data[action_key]["action_fields"]:
                    value = getattr(self, field)

                    if value is None or value == "":
                        continue

                    param_name = field.replace(action_key + "_", "")
                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )

            # Ensure result is a dictionary
            if not isinstance(result, dict):
                logger.error(f"Unexpected result type: {type(result)}, value: {result}")
                return {"error": f"Unexpected result type: {type(result)}"}

            if not result.get("successful"):
                message = result.get("data", {})
                message = message.get("message", {}) if isinstance(message, dict) else str(message)

                error_info = {"error": result.get("error", "No response")}
                if isinstance(message, str):
                    try:
                        parsed_message = json.loads(message)
                        if isinstance(parsed_message, dict) and "error" in parsed_message:
                            error_data = parsed_message["error"]
                            error_info = {
                                "error": {
                                    "code": error_data.get("code", "Unknown"),
                                    "message": error_data.get("message", "No error message"),
                                }
                            }
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Failed to parse error message as JSON: {e}")
                        error_info = {"error": str(message)}
                elif isinstance(message, dict) and "error" in message:
                    error_data = message["error"]
                    error_info = {
                        "error": {
                            "code": error_data.get("code", "Unknown"),
                            "message": error_data.get("message", "No error message"),
                        }
                    }

                return error_info

            result_data = result.get("data", [])

            if result_data is None:
                result_data = []
            elif isinstance(result_data, int | str | float | bool):
                logger.warning(f"Result data is a primitive type: {type(result_data)}, value: {result_data}")
                result_data = [{"value": result_data}]

            action_data = self._actions_data.get(action_key, {})

            def ensure_dict_list(data):
                """Ensure data is a list of dictionaries."""
                if isinstance(data, dict):
                    return [data]
                if isinstance(data, list):
                    dict_list = []
                    for item in data:
                        if isinstance(item, dict):
                            dict_list.append(item)
                        else:
                            dict_list.append({"value": item})
                    return dict_list
                return [{"value": data}]

            def convert_posts_list_to_indexed_dict(data):
                """Convert posts_list array to indexed dictionary."""
                if isinstance(data, list):
                    indexed_dict = {}
                    for i, item in enumerate(data):
                        indexed_dict[str(i)] = item
                    return [indexed_dict]
                return ensure_dict_list(data)

            if action_data.get("get_result_field"):
                result_field = action_data.get("result_field")
                if result_field:
                    found = self._find_key_recursively(result_data, result_field)
                    if found is not None and found != []:
                        converted = self._convert_pandas_to_python(found)
                        if result_field in ["posts_list", "children"]:
                            return convert_posts_list_to_indexed_dict(converted)
                        return ensure_dict_list(converted)

                converted_data = self._convert_pandas_to_python(result_data)
                return ensure_dict_list(converted_data)

            if result_data and isinstance(result_data, dict):
                converted_data = self._convert_pandas_to_python(result_data)
                if converted_data:
                    first_key = next(iter(converted_data))
                    return ensure_dict_list(converted_data[first_key])
                return []

            converted_data = self._convert_pandas_to_python(result_data)
            return ensure_dict_list(converted_data)
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else str(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)

    def set_default_tools(self):
        self._default_tools = {
            self.sanitize_action_name("REDDIT_CREATE_REDDIT_POST").replace(" ", "-"),
            self.sanitize_action_name("REDDIT_RETRIEVE_REDDIT_POST").replace(" ", "-"),
        }
