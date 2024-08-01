---
title: Data
sidebar_position: 3
slug: /components-data
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




## API Request {#23da589293f74016a1f70d6d7c0fdc55}


---


This component sends HTTP requests to the specified URLs.


Use this component to interact with external APIs or services and retrieve data. Ensure that the URLs are valid and that you configure the method, headers, body, and timeout correctly.


**Parameters:**

- **URLs:** The URLs to target.
- **Method:** The HTTP method, such as GET or POST.
- **Headers:** The headers to include with the request.
- **Body:** The data to send with the request (for methods like POST, PATCH, PUT).
- **Timeout:** The maximum time to wait for a response.

## Directory {#4fe56acaaac847029ace173dc793f8f4}


---


This component recursively retrieves files from a specified directory.


Use this component to retrieve various file types, such as text or JSON files, from a directory. Make sure to provide the correct path and configure the other parameters as needed.


**Parameters:**

- **Path:** The directory path.
- **Types:** The types of files to retrieve. Leave this blank to retrieve all file types.
- **Depth:** The level of directory depth to search.
- **Max Concurrency:** The maximum number of simultaneous file loading operations.
- **Load Hidden:** Set to true to include hidden files.
- **Recursive:** Set to true to enable recursive search.
- **Silent Errors:** Set to true to suppress exceptions on errors.
- **Use Multithreading:** Set to true to use multithreading in file loading.

## File {#d5d4bb78ce0a473d8a3b6a296d3e8383}


---


This component loads a file.


Use this component to load files, such as text or JSON files. Ensure you specify the correct path and configure other parameters as necessary.


**Parameters:**

- **Path:** The file path.
- **Silent Errors:** Set to true to prevent exceptions on errors.

## URL {#1cc513827a0942d6885b3a9168eabc97}


---


This component retrieves content from specified URLs.


Ensure the URLs are valid and adjust other parameters as needed. **Parameters:**

- **URLs:** The URLs to retrieve content from.

## Create Data {#aac4cad0cd38426191c2e7516285877b}


---


This component allows you to create a `Data` from a number of inputs. You can add as many key-value pairs as you want (as long as it is less than 15). Once you've picked that number you'll need to write the name of the Key and can pass `Text` values from other components to it.

