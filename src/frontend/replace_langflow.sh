#!/bin/bash

# Search for 'langflow' in React files excluding unwanted files
search_results=$(grep -rni --include=\*.{tsx,jsx,html} 'langflow' . | grep -vE '\.py$|test|key names|variable names|\.css')

# Check if we found any results
if [ -z "$search_results" ]; then
    echo "No occurrences of 'langflow' found in React files."
    exit 0
fi

echo "Found occurrences of 'langflow':"
echo "$search_results"

# Read each line of search results
while IFS= read -r line; do
    # Extract the file name and line number
    file_name=$(echo "$line" | cut -d':' -f1)
    line_number=$(echo "$line" | cut -d':' -f2)
    
    # Display the line with context
    echo "In $file_name (line $line_number):"
    echo "    $line"

    # Prompt the user for replacement
    read -p "Replace 'langflow' with 'Kendra Labs'? (y/n): " response

    if [[ "$response" == "y" ]]; then
        # Make the replacement in the file
        sed -i.bak "s/langflow/Kendra Labs/g" "$file_name"
        echo "'langflow' replaced with 'Kendra Labs' in $file_name."
    fi
done <<< "$search_results"

echo "Finished processing replacements."