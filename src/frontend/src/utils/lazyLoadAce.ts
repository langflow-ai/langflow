export async function lazyLoadAce() {
  await import("ace-builds/src-noconflict/ext-language_tools");
  await import("ace-builds/src-noconflict/mode-python");
  await import("ace-builds/src-noconflict/theme-github");
  await import("ace-builds/src-noconflict/theme-twilight");
}
