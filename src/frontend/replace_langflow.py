import os
import re

def find_langflow_occurrences(directory):
    """
    Finds all occurrences of "langflow" in React files within a directory.

    Args:
        directory: The directory to search within.

    Returns:
        A list of tuples, where each tuple contains: 
          - The file path where "langflow" was found. (important addition)
          - The line number where "langflow" was found (important addition).   - The line content containing "langflow".                                           

    Raises:                                           
      TypeError if input is not a string or if it's not a directory
      FileNotFoundError if the input doesn't exist                               

    """

    if not isinstance(directory, str):
        raise TypeError("Directory must be a string.")
    if not os.path.isdir(directory):                                                 
      raise FileNotFoundError(f"Directory '"+directory+"' not found.")

    occurrences = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.tsx', '.jsx', '.js', '.jsx.ts', '.ts')): # Check for React file extensions (important addition)                                                 
                  try:
                      filepath = os.path.join(root, file)

                     # More robustly read the whole file to prevent issues with partial matches caused by line breaks or other patterns

                      with open(filepath, 'r', errors='ignore') as f:   # Handle possible encoding issues if necessary  with error handling and opening mode 'r' for reading

                          for lineno, line in enumerate(f):

                              matches = re.finditer(r'"Langflow"', line) #More specific regex to prevent matching within strings like "langflowtext"                               

                              for match in matches:
                                  occurrences.append((filepath, lineno + 1, line.strip())) #line numbers start at 1 and we need the original line (added strip)

                  except UnicodeDecodeError:
                        print(f"Skipping file {filepath} due to UnicodeDecodeError.")

    return occurrences

# Example usage (replace with your directory):
if __name__ == "__main__":
    directory_to_search = "src/pages/AdminPage/LoginPage" # Replace with the actual path

    try:

        found_occurrences = find_langflow_occurrences(directory_to_search)

        for file, lineno ,originalLine in found_occurrences :  #Corrected parameter names for clarity

            print(f"\nFound 'langflow' in file: {file} , Line number: {lineno}")
            print(f"Line content: {originalLine}")
            #prompt user for input in loop
            confirmation = input(f"Replace 'langflow' with 'Kendra Labs' in this line [y/n]?: ")

            if confirmation.lower() == "y":  # more robust case matching                                                 
             with open(file, 'r') as originalFile:

               file_content = originalFile.read()

               updated_content = file_content.replace(originalLine,'"' + "Kendra Labs" + '"') #use the correct string to replace

             with open(file, 'w') as updatedFile:
               updatedFile.write(updated_content)

             print("Replacement successful.")

        if not found_occurrences:
          print("No occurrences of 'langflow' found.")

    except FileNotFoundError as e:
        print(f"Error: {e}")
