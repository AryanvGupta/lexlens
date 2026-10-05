import { expect, test } from "vitest";
import { name } from "../src/index.js";

test("module loads", () => {
  expect(name).toBe("lexlens-mcp-server");
});
