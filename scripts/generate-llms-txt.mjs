#!/usr/bin/env node

/**
 * Generate llms.txt from the docs/ directory structure.
 *
 * Reads all Markdown files under docs/, extracts YAML frontmatter
 * (summary, title), and produces a structured llms.txt file following
 * the llms.txt specification (https://llmstxt.org/).
 *
 * Usage:
 *   node scripts/generate-llms-txt.mjs              # Print to stdout
 *   node scripts/generate-llms-txt.mjs --write       # Write to docs/llms.txt
 */

import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

const DOCS_DIR = join(process.cwd(), "docs");
const OUTPUT_PATH = join(DOCS_DIR, "llms.txt");
const DOCS_BASE_URL = "https://docs.openclaw.ai";

const EXCLUDED_DIRS = new Set(["archive", "research", "zh-CN", "ja-JP", "ru", ".i18n", "assets", "images"]);

/** @param {string} dir @param {string} base @returns {Array<{path: string, fullPath: string}>} */
function walkMarkdownFiles(dir, base = dir) {
  if (!existsSync(dir) || !statSync(dir).isDirectory()) return [];
  const entries = readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (EXCLUDED_DIRS.has(entry.name)) continue;
      files.push(...walkMarkdownFiles(fullPath, base));
    } else if (entry.isFile() && (entry.name.endsWith(".md") || entry.name.endsWith(".mdx"))) {
      files.push({ path: relative(base, fullPath), fullPath });
    }
  }
  return files.toSorted((a, b) => a.path.localeCompare(b.path));
}

/** @param {string} fullPath @returns {{ title: string | null, summary: string | null }} */
function extractMeta(fullPath) {
  const raw = readFileSync(fullPath, "utf-8");
  const match = raw.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return { title: null, summary: null };

  const fm = match[1];
  const titleMatch = fm.match(/^title:\s*["']?(.+?)["']?\s*$/m);
  const summaryMatch = fm.match(/^summary:\s*["']?(.+?)["']?\s*$/m);

  return {
    title: titleMatch ? titleMatch[1].trim() : null,
    summary: summaryMatch ? summaryMatch[1].trim() : null,
  };
}

/** @param {string} filePath @returns {string} */
function pathToUrl(filePath) {
  let route = filePath.replace(/\.(md|mdx)$/, "").replace(/\/index$/, "");
  if (route === "index") route = "";
  return `${DOCS_BASE_URL}/${route}`;
}

// --- Categorize files into sections ---
const SECTION_MAP = [
  { prefix: "start/", label: "Getting started" },
  { prefix: "install/", label: "Installation" },
  { prefix: "concepts/", label: "Core concepts" },
  { prefix: "channels/", label: "Messaging channels" },
  { prefix: "providers/", label: "Model providers" },
  { prefix: "gateway/", label: "Gateway operations" },
  { prefix: "tools/", label: "Tools and automation" },
  { prefix: "automation/", label: "Automation" },
  { prefix: "nodes/", label: "Nodes, media, and voice" },
  { prefix: "platforms/", label: "Platforms" },
  { prefix: "web/", label: "Web interfaces" },
  { prefix: "cli/", label: "CLI reference" },
  { prefix: "plugins/", label: "Plugins" },
  { prefix: "security/", label: "Security" },
  { prefix: "reference/", label: "Technical reference" },
  { prefix: "help/", label: "Help and troubleshooting" },
  { prefix: "debug/", label: "Debugging" },
  { prefix: "diagnostics/", label: "Diagnostics" },
  { prefix: "design/", label: "Design" },
  { prefix: "experiments/", label: "Experiments" },
];

function categorize(filePath) {
  for (const { prefix, label } of SECTION_MAP) {
    if (filePath.startsWith(prefix)) return label;
  }
  return "Other";
}

// --- Main ---
if (!existsSync(DOCS_DIR)) {
  console.error("generate-llms-txt: missing docs directory. Run from repo root.");
  process.exit(1);
}

const files = walkMarkdownFiles(DOCS_DIR);
const sections = new Map();

for (const file of files) {
  const section = categorize(file.path);
  if (!sections.has(section)) sections.set(section, []);
  const meta = extractMeta(file.fullPath);
  sections.get(section).push({
    url: pathToUrl(file.path),
    title: meta.title || file.path.replace(/\.(md|mdx)$/, ""),
    summary: meta.summary || "",
  });
}

// --- Build output ---
const lines = [
  "# OpenClaw",
  "",
  "> OpenClaw is a self-hosted gateway that connects WhatsApp, Telegram, Discord, iMessage, Slack, and 20+ messaging channels to AI coding agents. Run a single Gateway process on your own machine and message your AI assistant from anywhere. It supports 50+ model providers, multi-agent routing, voice, camera, skills, and a plugin system.",
  "",
  "- Documentation: https://docs.openclaw.ai",
  "- Source code: https://github.com/openclaw/openclaw",
  "- Community: https://discord.com/invite/clawd",
  "- Skills marketplace: https://clawhub.com",
  "- License: MIT",
  "",
];

for (const [section, entries] of sections) {
  if (section === "Other" && entries.length === 0) continue;
  lines.push(`## ${section}`, "");
  for (const entry of entries) {
    const suffix = entry.summary ? `: ${entry.summary}` : "";
    lines.push(`- [${entry.title}](${entry.url})${suffix}`);
  }
  lines.push("");
}

const output = lines.join("\n");

if (process.argv.includes("--write")) {
  writeFileSync(OUTPUT_PATH, output, "utf-8");
  console.log(`Wrote ${OUTPUT_PATH} (${files.length} files, ${sections.size} sections)`);
} else {
  console.log(output);
  console.log(`\n--- ${files.length} files, ${sections.size} sections ---`);
  console.log(`Run with --write to save to ${OUTPUT_PATH}`);
}
