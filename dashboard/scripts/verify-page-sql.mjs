/**
 * Run every SQL block on a page against the warehouse, without building the site.
 *
 *   npm run fetch                       # once, to get ../data/warehouse.duckdb
 *   npm run verify                      # every page
 *   npm run verify pages/scorecard.md   # one page
 *
 * `evidence build` is the real check, but it is slow, and in a sandbox without
 * access to extensions.duckdb.org it cannot run at all. The queries are the part
 * that actually goes wrong: a renamed column, a schema that moved, a filter that
 * matches nothing. This runs them and prints what came back.
 *
 * Two things Evidence does are reproduced here: every file in sources/warehouse
 * becomes a table named after it, and ${query_name} inlines that query. Inputs
 * are substituted with the empty string, which is what a page sees while it is
 * being prerendered, so a page that cannot survive that fails here too.
 */
import { readFileSync, readdirSync } from "node:fs";
import { basename, join } from "node:path";
import { Database } from "duckdb-async";

const SOURCES = "sources/warehouse";
const WAREHOUSE = "../data/warehouse.duckdb";
const SQL_BLOCK = /```sql\s+(\w+)\n([\s\S]*?)```/g;
const QUERY_REF = /\$\{(\w+)\}/g;
const INPUT_REF = /\$\{inputs\.[\w.]+\}/g;

function pagesToCheck() {
  const given = process.argv.slice(2);
  if (given.length) return given;

  const found = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (entry.name.endsWith(".md")) found.push(path);
    }
  };
  walk("pages");
  return found;
}

const db = await Database.create(":memory:");
const conn = await db.connect();
await conn.all(`attach '${WAREHOUSE}' as warehouse (read_only)`);
await conn.all("use memory");

for (const file of readdirSync(SOURCES).filter((name) => name.endsWith(".sql"))) {
  const table = basename(file, ".sql");
  const query = readFileSync(join(SOURCES, file), "utf8")
    .replace(/;\s*$/, "")
    // The source files read the warehouse as the default database. Here it is
    // attached alongside an in-memory one, so the schema needs qualifying.
    .replaceAll("marts.", "warehouse.marts.");
  await conn.all(`create or replace view memory.main.${table} as ${query}`);
}

let failures = 0;

for (const page of pagesToCheck()) {
  const blocks = [...readFileSync(page, "utf8").matchAll(SQL_BLOCK)].map((match) => ({
    name: match[1],
    sql: match[2],
  }));
  if (blocks.length === 0) continue;

  const named = Object.fromEntries(blocks.map((block) => [block.name, block.sql]));

  const resolve = (sql, depth = 0) => {
    if (depth > 8) throw new Error(`${page}: query references are cyclic`);
    return sql
      .replace(INPUT_REF, "")
      .replace(QUERY_REF, (_, name) => {
        if (!named[name]) throw new Error(`no query named ${name} on this page`);
        return `(${resolve(named[name], depth + 1)})`;
      });
  };

  console.log(`\n${page}`);
  for (const block of blocks) {
    // A dynamic route's params have no value outside a request, so its pages
    // are checked by hand rather than pretended at here.
    if (block.sql.includes("${params.")) {
      console.log(`  ${block.name.padEnd(14)} skipped, needs route params`);
      continue;
    }
    try {
      const rows = await conn.all(resolve(block.sql));
      const first = rows[0]
        ? Object.entries(rows[0])
            .slice(0, 3)
            .map(([key, value]) => `${key}=${value}`)
            .join("  ")
        : "no rows";
      console.log(`  ${block.name.padEnd(14)} ${String(rows.length).padStart(5)} rows  ${first}`);
    } catch (error) {
      failures += 1;
      console.log(`  ${block.name.padEnd(14)} FAILED  ${error.message.split("\n")[0]}`);
    }
  }
}

await conn.close();
await db.close();

if (failures > 0) {
  console.error(`\n${failures} quer${failures === 1 ? "y" : "ies"} failed.`);
  process.exit(1);
}
