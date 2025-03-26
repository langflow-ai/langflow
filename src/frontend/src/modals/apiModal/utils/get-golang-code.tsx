import { GetCodeType } from "@/types/tweaks";

/**
 * Function to get the Golang code for the API
 * @param {string} flowName - The current flow name
 * @param {any[]} tweaksBuildedObject - The tweaks
 * @param {boolean} activeTweaks - Whether tweaks are active
 * @returns {string} - The Golang code snippet
 */
export default function getGolangCode({
  flowName,
  tweaksBuildedObject,
  activeTweaks,
}: GetCodeType): string {
  // Format tweaks for Go syntax
  let tweaksString = "langflowclient.Options{}";
  if (
    activeTweaks &&
    tweaksBuildedObject &&
    Object.keys(tweaksBuildedObject).length > 0
  ) {
    tweaksString = `langflowclient.Options${JSON.stringify(
      tweaksBuildedObject,
      null,
      2,
    )
      .replace(/"([^"]+)":/g, "$1:") // Remove quotes from keys
      .replace(/"/g, `'`) // Convert double quotes to single quotes
      .replace(/,/g, ",\n")}`; // Format commas
  }

  return `package main

import (
    "fmt"
    "log"

    "github.com/devalexandre/langflowgo/langflowclient"
)

func main() {
    client := langflowclient.LangflowClient{
        BaseURL: "http://127.0.0.1:7860",
        APIKey:  "your_api_key_here",
    }

    tweaks := ${tweaksString}

    response, err := client.RunFlow("${flowName}", "User message", tweaks, ${activeTweaks},
        func(data map[string]interface{}) {
            fmt.Println("Received:", data)
        },
        func(message string) {
            fmt.Println("Stream Closed:", message)
        },
        func(err error) {
            fmt.Println("Stream Error:", err)
        },
    )

    if err != nil {
        log.Fatal(err)
    }

    fmt.Println("Flow completed successfully:", response)
}`;
}
