#!/usr/bin/env node
"use strict";

const { execFileSync, spawnSync } = require("node:child_process");
const readline = require("node:readline");
const path = require("node:path");

const repositoryRoot = path.resolve(__dirname, "..");
const messagePrefix = "curatorMD-dev_";
const versionPattern = /^curatorMD-dev_(\d{1,2})\.(\d{1,2})\.(\d{1,2})\.(\d{2})(?:$|[ :].*)/;

function readGit(args) {
  return execFileSync("git", args, {
    cwd: repositoryRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

function parseVersion(message) {
  const match = versionPattern.exec(message);
  if (!match) {
    return null;
  }

  const parts = match.slice(1).map(Number);
  return parts.every((part) => part <= 99) ? parts : null;
}

function formatMessage(parts) {
  const [major, minor, range, sequence] = parts;
  const rangeText = range > 0 || sequence === 0 ? String(range).padStart(2, "0") : "0";
  return `${messagePrefix}${major}.${minor}.${rangeText}.${String(sequence).padStart(2, "0")}`;
}

function nextMessage(previousMessage) {
  const parts = parseVersion(previousMessage);
  if (!parts) {
    throw new Error(`Latest numbered commit message is invalid: ${previousMessage}`);
  }

  for (let index = parts.length - 1; index >= 0; index -= 1) {
    if (parts[index] < 99) {
      parts[index] += 1;
      return formatMessage(parts);
    }
    parts[index] = 0;
  }

  throw new Error("The four-part 00-99 commit sequence is exhausted.");
}

function runGit(args) {
  const result = spawnSync("git", args, {
    cwd: repositoryRoot,
    stdio: "inherit",
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`git ${args.join(" ")} failed with exit code ${result.status}`);
  }
}

async function promptForMessage(message) {
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    throw new Error("Run npm run update-git in an interactive terminal.");
  }

  const prompt = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: true,
  });
  prompt.setPrompt("Commit message (Enter accepts; edit after version if needed): ");
  prompt.prompt();
  prompt.write(message);

  const enteredMessage = await new Promise((resolve, reject) => {
    prompt.once("line", resolve);
    prompt.once("SIGINT", () => reject(new Error("Commit cancelled.")));
  }).finally(() => prompt.close());

  const selectedMessage = String(enteredMessage).trim() || message;
  if (
    selectedMessage !== message &&
    !selectedMessage.startsWith(`${message}:`) &&
    !selectedMessage.startsWith(`${message} `)
  ) {
    throw new Error(`Keep the automatically incremented version prefix: ${message}`);
  }
  return selectedMessage;
}

async function main() {
  const worktreeRoot = readGit(["rev-parse", "--show-toplevel"]);
  if (path.resolve(worktreeRoot) !== repositoryRoot) {
    throw new Error("Run this script from the CuratorMD repository root.");
  }

  readGit(["symbolic-ref", "--short", "HEAD"]);
  readGit(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]);
  readGit(["config", "user.name"]);
  readGit(["config", "user.email"]);

  const subjects = readGit(["log", "--format=%s"])
    .split("\n")
    .filter((subject) => subject.startsWith(messagePrefix));
  if (subjects.length === 0) {
    throw new Error(`No prior ${messagePrefix} commit was found.`);
  }
  const message = nextMessage(subjects[0]);

  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    throw new Error("Run npm run update-git in an interactive terminal.");
  }

  runGit(["add", "."]);
  if (readGit(["diff", "--cached", "--name-only"]) === "") {
    throw new Error("No staged changes to commit.");
  }

  console.log(`Staged all non-ignored repository changes.`);
  const selectedMessage = await promptForMessage(message);
  runGit(["commit", "-m", selectedMessage]);
  runGit(["push"]);
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}

module.exports = { formatMessage, nextMessage, parseVersion };
