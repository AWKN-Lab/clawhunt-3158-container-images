// 最小构建脚本（#3158）：把 public/ 原样拷到 dist/。
// 真实前端（React + TypeScript + TDesign）把此处换成 vite build /
// tsc 构建命令即可；Dockerfile 的构建阶段不需改。
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "public");
const out = join(root, "dist");

if (!existsSync(src)) {
  console.error("public/ not found, nothing to build");
  process.exit(1);
}
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
cpSync(src, out, { recursive: true });
console.log(`built ${out}`);
