import { describe, expect, test } from "vitest";
import { GuardError, assertExplainWrapper, assertSingleSelect } from "../src/sql/guard.js";

const rejects = (sql: string) => expect(assertSingleSelect(sql)).rejects.toBeInstanceOf(GuardError);

describe("assertSingleSelect: rejected", () => {
  test("DROP TABLE", () => rejects("DROP TABLE film"));
  test("SELECT pg_sleep(60)", () => rejects("SELECT pg_sleep(60)"));
  test("pg_sleep in a subquery or schema-qualified", () => rejects("SELECT * FROM film WHERE (SELECT pg_catalog.pg_sleep(10)) IS NULL"));
  test("multi-statement", () => rejects("SELECT 1; DROP TABLE film"));
  test("two harmless selects", () => rejects("SELECT 1; SELECT 2"));
  test("INSERT / UPDATE / DELETE", async () => {
    await rejects("INSERT INTO film(title) VALUES ('x')");
    await rejects("UPDATE film SET title = 'x'");
    await rejects("DELETE FROM film");
  });
  test("data-modifying CTE", () => rejects("WITH d AS (DELETE FROM film RETURNING *) SELECT * FROM d"));
  test("SELECT INTO", () => rejects("SELECT * INTO newfilm FROM film"));
  test("FOR UPDATE", () => rejects("SELECT * FROM film FOR UPDATE"));
  test("dangerous functions", async () => {
    await rejects("SELECT nextval('film_film_id_seq')");
    await rejects("SELECT pg_read_file('/etc/passwd')");
    await rejects("SELECT set_config('statement_timeout','0',false)");
    await rejects("SELECT lo_import('/etc/passwd')");
  });
  test("empty, whitespace, syntax error, oversized", async () => {
    await rejects("");
    await rejects("   ");
    await rejects("SELEC 1");
    await rejects(`SELECT ${"1,".repeat(3000)}1`);
  });
  test("keywords inside strings/comments do not matter, real statements do", async () => {
    await rejects("SELECT 1 /* harmless */; DROP TABLE film");
  });
});

describe("assertSingleSelect: accepted", () => {
  test.each([
    "SELECT * FROM film WHERE film_id = 1",
    "SELECT * FROM film;",
    "SELECT 'DROP TABLE film; pg_sleep(60)' AS s",
    "-- DROP TABLE film\nSELECT 1",
    "WITH x AS (SELECT film_id FROM film) SELECT count(*) FROM x",
    "SELECT f.title, count(*) FROM film f JOIN inventory i USING (film_id) GROUP BY f.title",
  ])("%s", (sql) => expect(assertSingleSelect(sql)).resolves.toBeUndefined());
});

test("assertExplainWrapper accepts one EXPLAIN and rejects a smuggled second statement", async () => {
  await expect(assertExplainWrapper("EXPLAIN (FORMAT JSON) SELECT 1")).resolves.toBeUndefined();
  await expect(assertExplainWrapper("EXPLAIN (FORMAT JSON) SELECT 1; DROP TABLE film")).rejects.toBeInstanceOf(GuardError);
});
