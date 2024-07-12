---
title: ❗️ Common Installation Issues
sidebar_position: 3
slug: /getting-started-common-installation-issues
---



This is a list of possible issues that you may encounter when installing Langflow and how to solve them.


---


```bash
> No module named 'langflow.__main__' 
```

1. Run `python -m langflow run` instead of `langflow run`.
2. If that doesn't work, reinstall Langflow with `_python -m pip install langflow --pre -U`.
3. If that doesn't work, reinstall Langflow and its dependencies with `python -m pip install langflow --pre -U --force-reinstall`.

When you try to run Langflow using the command `langflow run`, you may encounter the following error:


```bash
> langflow runTraceback (most recent call last): File ".../langflow", line 5, in <module>  from langflow.__main__ import mainModuleNotFoundError: No module named 'langflow.__main__'
```


There are two possible reasons for this error:

1. You've installed Langflow using `pip install langflow` but you already had a previous version of Langflow installed in your system. In this case, you might be running the wrong executable. To solve this issue, run the correct executable by running `python -m langflow run` instead of `langflow run`. If that doesn't work, try uninstalling and reinstalling Langflow with `python -m pip install langflow --pre -U`.
2. Some version conflicts might have occurred during the installation process. Run `python -m pip install langflow --pre -U --force-reinstall` to reinstall Langflow and its dependencies.

```bash
> Something went wrong running migrations. Please, run 'langflow migration --fix'
```


Clear the cache by deleting the contents of the cache folder.


This folder can be found at:

- **Linux or WSL2 on Windows**: `home/<username>/.cache/langflow/`
- **MacOS**: `/Users/<username>/Library/Caches/langflow/`

This error can occur during Langflow upgrades when the new version can't override `langflow-pre.db` in `.cache/langflow/`. Clearing the cache removes this file but will also erase your settings.


If you wish to retain your files, back them up before clearing the folder.

