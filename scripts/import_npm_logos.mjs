#!/usr/bin/env node
// Mirror the logos the `ncaa-team-logos` npm package carries into the
// dashboard's static files, as PNGs named by warehouse team id.
//
// This is the second source for dashboard/static/logos, beside
// scripts/fetch_logos.py. That script is the general one: it mirrors every
// team the warehouse has a `team_logo_url` for, but the published warehouse
// has none yet, because the team dimension has not been re-extracted since
// the extractor learned the column. This one covers the forty programs the
// package draws, which is most of what the boards put at the top of a list.
// When fetch_logos.py does run, it skips any team that already has a file,
// so the two never fight; `--force` there replaces these with the source's.
//
// The package ships each logo as a React component wrapping plain SVG. This
// renders each one to markup, drops the editor attributes some of them carry
// (an `inkscape:` attribute with no namespace declared makes the file
// unparseable on its own), and draws it into a 256px transparent square with
// a headless browser, because a PNG is what the pages probe for.
//
// The team ids below were matched by name against marts.mart_team_season and
// checked by eye on a contact sheet. The package's `ncca` component is the
// NCAA's own mark, not a team, and is left out.
//
// Needs react, react-dom and ncaa-team-logos installed in a scratch
// directory, and Playwright with a Chromium it can launch:
//
//   mkdir -p /tmp/logos && (cd /tmp/logos && npm init -y >/dev/null &&
//     npm install react@19.0.0 react-dom@19.0.0 ncaa-team-logos@1.8.0)
//   node scripts/import_npm_logos.mjs /tmp/logos
//
// Run from the repository root. Existing files are left alone unless
// --force is given.

import { createHash } from "node:crypto";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const PACKAGE = "ncaa-team-logos";
const SIZE = 256;
const PADDING = 12;

// Package component file -> warehouse team id.
const TEAMS = {
    alabama: ["5", "Alabama Crimson Tide"],
    auburn: ["16", "Auburn Tigers"],
    baylor: ["20", "Baylor Bears"],
    boisestate: ["25", "Boise State Broncos"],
    clemson: ["52", "Clemson Tigers"],
    colorado: ["56", "Colorado Buffaloes"],
    creighton: ["61", "Creighton Bluejays"],
    duke: ["72", "Duke Blue Devils"],
    florida: ["87", "Florida Gators"],
    fsu: ["90", "Florida State Seminoles"],
    georgia: ["98", "Georgia Bulldogs"],
    gonzaga: ["102", "Gonzaga Bulldogs"],
    iowastate: ["125", "Iowa State Cyclones"],
    kansas: ["131", "Kansas Jayhawks"],
    kansasstate: ["132", "Kansas State Wildcats"],
    lsu: ["136", "LSU Tigers"],
    marquette: ["157", "Marquette Golden Eagles"],
    memphis: ["163", "Memphis Tigers"],
    miami: ["168", "Miami Hurricanes"],
    michigan: ["170", "Michigan Wolverines"],
    ndsu: ["202", "North Dakota State Bison"],
    notredame: ["213", "Notre Dame Fighting Irish"],
    ohiostate: ["216", "Ohio State Buckeyes"],
    oklahoma: ["217", "Oklahoma Sooners"],
    oregon: ["223", "Oregon Ducks"],
    oregonstate: ["224", "Oregon State Beavers"],
    pennstate: ["226", "Penn State Nittany Lions"],
    stjohns: ["279", "St. John's Red Storm"],
    tcu: ["287", "TCU Horned Frogs"],
    texas: ["295", "Texas Longhorns"],
    texasam: ["293", "Texas A&M Aggies"],
    texastech: ["298", "Texas Tech Red Raiders"],
    tulane: ["303", "Tulane Green Wave"],
    uccon: ["314", "UConn Huskies"],
    ucf: ["312", "UCF Knights"],
    ucla: ["313", "UCLA Bruins"],
    unc: ["200", "North Carolina Tar Heels"],
    usc: ["323", "USC Trojans"],
    villanova: ["338", "Villanova Wildcats"],
    washington: ["343", "Washington Huskies"],
};

const [scratch, ...flags] = process.argv.slice(2);
if (!scratch) {
    console.error("Usage: node scripts/import_npm_logos.mjs <dir with the packages installed> [--force]");
    process.exit(1);
}
const force = flags.includes("--force");
const out = path.resolve("dashboard/static/logos");

const require = createRequire(path.join(path.resolve(scratch), "noop.js"));
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const version = require(`${PACKAGE}/package.json`).version;
const { chromium } = createRequire(import.meta.url)("playwright");

/** The component's SVG, with attributes from an undeclared namespace removed. */
function svgFor(file) {
    const component = require(`${PACKAGE}/dist/logos/${file}.js`).default;
    return renderToStaticMarkup(React.createElement(component)).replace(
        /\s(?:inkscape|sodipodi):[\w-]+="[^"]*"/g,
        "",
    );
}

const manifestPath = path.join(out, "manifest.json");
const manifest = fs.existsSync(manifestPath)
    ? JSON.parse(fs.readFileSync(manifestPath, "utf8"))
    : {};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: SIZE, height: SIZE } });
let written = 0;

for (const [file, [teamId, teamName]] of Object.entries(TEAMS)) {
    const target = path.join(out, `${teamId}.png`);
    if (fs.existsSync(target) && !force) {
        console.log(`  skip ${teamName}: ${teamId}.png is already there`);
        continue;
    }

    const svg = Buffer.from(svgFor(file)).toString("base64");
    await page.setContent(
        `<html><body style="margin:0;background:transparent">
         <img id="logo" src="data:image/svg+xml;base64,${svg}"
              style="position:absolute;left:${PADDING}px;top:${PADDING}px;
                     width:${SIZE - 2 * PADDING}px;height:${SIZE - 2 * PADDING}px;
                     object-fit:contain"></body></html>`,
    );
    const loaded = await page.$eval("#logo", (img) => img.decode().then(() => img.naturalWidth > 0, () => false));
    if (!loaded) {
        console.error(`  MISS ${teamName}: ${file} did not render`);
        continue;
    }

    const png = await page.screenshot({ omitBackground: true, type: "png" });
    fs.writeFileSync(target, png);
    manifest[teamId] = {
        team_name: teamName,
        path: `/logos/${teamId}.png`,
        source: `npm:${PACKAGE}@${version}/dist/logos/${file}.js`,
        bytes: png.length,
        sha256: createHash("sha256").update(png).digest("hex"),
    };
    written += 1;
    console.log(`  ${teamName} -> ${teamId}.png (${png.length.toLocaleString()} bytes)`);
}

await browser.close();
const sorted = Object.fromEntries(
    Object.entries(manifest).sort(([a], [b]) => Number(a) - Number(b)),
);
fs.writeFileSync(manifestPath, `${JSON.stringify(sorted, null, 2)}\n`);
console.log(`Wrote ${written} logos into ${path.relative(process.cwd(), out)}.`);
