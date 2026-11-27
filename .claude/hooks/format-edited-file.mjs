// Formats and lints each JavaScript or TypeScript file an agent edits, right after the edit
// (a Claude Code hook).
//
// Claude Code runs this after every Edit or Write (.claude/settings.json, "PostToolUse") and
// passes the tool call as JSON on stdin. For a .js, .mjs, .cjs, .ts or .tsx file it runs
// `eslint --fix`. When problems remain, it prints them and exits 2, so the agent sees them and
// fixes them now, instead of at the end-of-change checks. Any other file is left alone.

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { extname } from "node:path";

const PROBLEMS_FOR_THE_AGENT = 2; // Claude Code shows a hook's stderr to the agent on exit code 2
const LINTED = new Set([".js", ".mjs", ".cjs", ".ts", ".tsx"]);

/** The file the tool call edited, or null when the input names no file. */
function editedFile(hookInput) {
  try {
    return JSON.parse(hookInput)?.tool_input?.file_path ?? null;
  } catch {
    return null; // not JSON: nothing to format
  }
}

const path = editedFile(readFileSync(0, "utf8"));
if (path && LINTED.has(extname(path)) && existsSync(path)) {
  const lint = spawnSync("bunx", ["eslint", "--fix", path], { encoding: "utf8", shell: true });
  if (lint.status !== 0) {
    process.stderr.write(lint.stdout + lint.stderr);
    process.exit(PROBLEMS_FOR_THE_AGENT);
  }
}
