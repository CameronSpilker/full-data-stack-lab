// Write the parquet files Evidence promises but does not produce for a source
// that returned no rows.
//
// `evidence sources` writes one parquet per source and lists it in
// static/data/manifest.json. A source that returns zero rows is the exception:
// buildMultipartParquet returns early without writing anything, and the
// filename is added to the manifest regardless. `evidence build` then creates
// a view over a file that is not there and the whole build dies on it:
//
//     Invalid Input Error: File 'warehouse_upcoming_games.parquet'
//     too small to be a Parquet file
//
// One source here is empty for most of the year. mart_upcoming_games holds the
// fixtures still to be played, and from April until the autumn there are none,
// so the site would be unbuildable for the whole offseason. The picks page
// already knows how to draw that: it reads the season phase and shows a
// labelled placeholder. It needs the query to return no rows, not to explode.
//
// So a promised file that does not exist is written here, with the columns the
// source declared and none of the rows. The schema comes from the
// .schema.json Evidence wrote beside it, and the DuckDB types are the ones
// Evidence itself maps those to.
//
// A source with rows is untouched, which is every source on a normal day, so
// this is a no-op in season and in CI.

import { mkdir, readFile, stat } from "node:fs/promises";
import path from "node:path";

import { DuckDBInstance } from "@duckdb/node-api";

const TEMPLATE = ".evidence/template";
const MANIFEST = path.join(TEMPLATE, "static/data/manifest.json");

// Evidence's own mapping, from columnsToScore in @evidence-dev/universal-sql.
// A date is a TIMESTAMP there rather than a DATE, so it is one here too.
const DUCKDB_TYPE = {
    number: "DOUBLE",
    boolean: "BOOLEAN",
    date: "TIMESTAMP",
    string: "VARCHAR",
};

async function exists(file) {
    try {
        await stat(file);
        return true;
    } catch {
        return false;
    }
}

async function readManifest() {
    try {
        return JSON.parse(await readFile(MANIFEST, "utf8"));
    } catch (error) {
        if (error.code === "ENOENT") {
            console.error(`No manifest at ${MANIFEST}. Run \`npm run sources\` first.`);
            process.exit(1);
        }
        throw error;
    }
}

function selectOfNoRows(columns) {
    const projection = columns
        .map(({ name, evidenceType }) => {
            const type = DUCKDB_TYPE[evidenceType] ?? DUCKDB_TYPE.string;
            return `cast(null as ${type}) as "${name.replaceAll('"', '""')}"`;
        })
        .join(", ");

    // No FROM, and a predicate that is never true: the column names and types
    // survive, the rows do not.
    return `select ${projection} where false`;
}

async function main() {
    const manifest = await readManifest();
    const missing = [];

    for (const [source, files] of Object.entries(manifest.renderedFiles ?? {})) {
        for (const file of files) {
            const parquet = path.join(TEMPLATE, file);
            if (await exists(parquet)) continue;

            const schema = parquet.replace(/\.parquet$/, ".schema.json");
            if (!(await exists(schema))) {
                console.error(
                    `${source}: ${file} is missing and so is its schema, so there is ` +
                        "nothing to write it from.",
                );
                process.exit(1);
            }

            missing.push({ source, parquet, schema });
        }
    }

    if (!missing.length) {
        console.log("Every source in the manifest wrote its parquet.");
        return;
    }

    const instance = await DuckDBInstance.create(":memory:");
    const connection = await instance.connect();

    for (const { source, parquet, schema } of missing) {
        const columns = JSON.parse(await readFile(schema, "utf8"));
        await mkdir(path.dirname(parquet), { recursive: true });

        const target = parquet.replaceAll("'", "''");
        await connection.run(
            `copy (${selectOfNoRows(columns)}) to '${target}' (format parquet, codec 'zstd')`,
        );

        console.log(
            `${source}: wrote ${path.basename(parquet)} with ` +
                `${columns.length} columns and no rows.`,
        );
    }

    // The manifest needs no edit. It named these files all along; they exist
    // now.
}

await main();
