// Live check: spawn the built server over stdio and call both tools against a running rag-api.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const client = new Client({ name: "e2e", version: "0" });
await client.connect(
  new StdioClientTransport({ command: process.execPath, args: ["dist/index.js"], env: process.env }),
);
for (const [name, args] of [
  ["search_legal", { query: "When is an invention too obvious to be patented?", k: 2 }],
  ["ask_legal", { question: "What is the federal minimum wage?" }],
  ["ask_legal", { question: "How many years does a patent term last from filing?" }],
]) {
  const r = await client.callTool({ name, arguments: args });
  console.log(`--- ${name} isError=${!!r.isError}\n${r.content[0].text.slice(0, 700)}\n`);
}
await client.close();
