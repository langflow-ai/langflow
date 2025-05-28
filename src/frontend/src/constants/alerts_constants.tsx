// ERROR
export const MISSED_ERROR_ALERT = "Oops! Looks like you missed something";
export const INCOMPLETE_LOOP_ERROR_ALERT =
  "The flow has an incomplete loop. Check your connections and try again.";
export const INVALID_FILE_ALERT =
  "Please select a valid file. Only these file types are allowed:";
export const CONSOLE_ERROR_MSG = "Error occurred while uploading file";
export const CONSOLE_SUCCESS_MSG = "File uploaded successfully";
export const INFO_MISSING_ALERT =
  "Oops! Looks like you missed some required information:";
export const FUNC_ERROR_ALERT = "There is an error in your function";
export const IMPORT_ERROR_ALERT = "There is an error in your imports";
export const BUG_ALERT = "Something went wrong, please try again";
export const CODE_ERROR_ALERT =
  "There is something wrong with this code, please review it";
export const CHAT_ERROR_ALERT =
  "Please build the flow again before using the chat.";
export const MSG_ERROR_ALERT = "There was an error sending the message";
export const PROMPT_ERROR_ALERT =
  "There is something wrong with this prompt, please review it";
export const API_ERROR_ALERT =
  "There was an error saving the API Key, please try again.";
export const USER_DEL_ERROR_ALERT = "Error on delete user";
export const USER_EDIT_ERROR_ALERT = "Error on edit user";
export const USER_ADD_ERROR_ALERT = "Error when adding new user";
export const SIGNIN_ERROR_ALERT = "Error signing in";
export const DEL_KEY_ERROR_ALERT = "Error on delete key";
export const DEL_KEY_ERROR_ALERT_PLURAL = "Error on delete keys";
export const UPLOAD_ERROR_ALERT = "Error uploading file";
export const WRONG_FILE_ERROR_ALERT = "Invalid file type";
export const UPLOAD_ALERT_LIST = "Please upload a JSON file";
export const INVALID_SELECTION_ERROR_ALERT = "Invalid selection";
export const EDIT_PASSWORD_ERROR_ALERT = "Error changing password";
export const EDIT_PASSWORD_ALERT_LIST = "Passwords do not match";
export const SAVE_ERROR_ALERT = "Error saving changes";
export const PROFILE_PICTURES_GET_ERROR_ALERT =
  "Error retrieving profile pictures";
export const SIGNUP_ERROR_ALERT = "Error signing up";
export const APIKEY_ERROR_ALERT = "API Key Error";
export const NOAPI_ERROR_ALERT =
  "You don't have an API Key. Please add one to use the Langflow Store.";
export const INVALID_API_ERROR_ALERT =
  "Your API Key is not valid. Please add a valid API Key to use the Langflow Store.";
export const COMPONENTS_ERROR_ALERT = "Error getting components.";

// NOTICE
export const NOCHATOUTPUT_NOTICE_ALERT =
  "There is no ChatOutput Component in the flow.";
export const API_WARNING_NOTICE_ALERT =
  "Warning: Critical data, JSON file may include API keys.";
export const COPIED_NOTICE_ALERT = "API Key copied!";
export const TEMP_NOTICE_ALERT = "Your template does not have any variables.";

// SUCCESS
export const CODE_SUCCESS_ALERT = "Code is ready to run";
export const PROMPT_SUCCESS_ALERT = "Prompt is ready";
export const API_SUCCESS_ALERT = "Success! Your API Key has been saved.";
export const USER_DEL_SUCCESS_ALERT = "Success! User deleted!";
export const USER_EDIT_SUCCESS_ALERT = "Success! User edited!";
export const USER_ADD_SUCCESS_ALERT = "Success! New user added!";
export const DEL_KEY_SUCCESS_ALERT = "Success! Key deleted!";
export const DEL_KEY_SUCCESS_ALERT_PLURAL = "Success! Keys deleted!";
export const FLOW_BUILD_SUCCESS_ALERT = `Flow built successfully`;
export const SAVE_SUCCESS_ALERT = "Changes saved successfully!";
export const INVALID_FILE_SIZE_ALERT = (maxSizeMB) => {
  return `The file size is too large. Please select a file smaller than ${maxSizeMB}.`;
};
