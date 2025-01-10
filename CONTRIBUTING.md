# Contributing to Langflow

This guide is intended to help you get started contributing to Langflow.
As an open-source project in a rapidly developing field, we are extremely open
to contributions, whether it be in the form of a new feature, improved infra, or better documentation.

To contribute to this project, please follow the [fork and pull request](https://docs.github.com/en/get-started/quickstart/contributing-to-projects) workflow.

## Reporting bugs or suggesting improvements

Our [GitHub issues](https://github.com/langflow-ai/langflow/issues) page is kept up to date
with bugs, improvements, and feature requests. There is a taxonomy of labels to help
with sorting and discovery of issues of interest. [See this page](https://github.com/langflow-ai/langflow/labels) for an overview of
the system we use to tag our issues and pull requests.

If you're looking for help with your code, consider posting a question on the
[GitHub Discussions board](https://github.com/langflow-ai/langflow/discussions). Please
understand that we won't be able to provide individual support via email. We
also believe that help is much more valuable if it's **shared publicly**,
so that more people can benefit from it.

- **Describing your issue:** Try to provide as many details as possible. What
  exactly goes wrong? _How_ is it failing? Is there an error?
  "XY doesn't work" usually isn't that helpful for tracking down problems. Always
  remember to include the code you ran and if possible, extract only the relevant
  parts and don't just dump your entire script. This will make it easier for us to
  reproduce the error.

- **Sharing long blocks of code or logs:** If you need to include long code,
  logs or tracebacks, you can wrap them in `<details>` and `</details>`. This
  [collapses the content](https://developer.mozilla.org/en/docs/Web/HTML/Element/details)
  so it only becomes visible on click, making the issue easier to read and follow.

## Contributing code and documentation

You can develop Langflow locally and contribute to the Project!

See [DEVELOPMENT.md](DEVELOPMENT.md) for instructions on setting up and using a development environment.

## Opening a pull request

Once you wrote and manually tested your change, you can start sending the patch to the main repository.

- Open a new GitHub pull request with the patch against the `main` branch.
- Ensure the PR title follows semantic commits conventions.
  - For example, `feat: add new feature`, `fix: correct issue with X`.
- Ensure the PR description clearly describes the problem and solution. Include the relevant issue number if applicable.
