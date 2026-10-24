# Team logos

Mirrored here by `scripts/fetch_logos.py`, served by the dashboard at `/logos`.

The rule every page relies on is that a team with a mirrored logo has it at
`/logos/<team_id>.png`, where `team_id` is the same id the marts use. There is
no lookup: a page builds the path from the id it already has.

What a page renders, though, is the team's initials in the team's own colour,
and the logo replaces them in the browser once it has loaded. That order is
load-bearing. SvelteKit prerenders these pages and its crawler follows an
`img src` exactly as it follows a link, so a logo path written into the
server-rendered markup fails the whole build on the first team whose file is
not there. Probing from the browser instead means a missing logo is invisible
and costs the build nothing, which is what lets the mirror be partial.

`manifest.json` records what resolved, from where, and the sha256 of each file.
Nothing reads it at build time. It is there so a logo that changes upstream is
a visible diff rather than a silent one.

## Where they come from

Two sources, recorded per file in `manifest.json`:

- `scripts/import_npm_logos.mjs` draws the forty programs the
  [`ncaa-team-logos`](https://www.npmjs.com/package/ncaa-team-logos) npm
  package carries (version 1.8.0). That covers most of the teams the boards
  put at the top of a list. The script's header says how to run it and how
  its team ids were matched.
- `scripts/fetch_logos.py`, below, mirrors every team the warehouse has a
  `team_logo_url` for. The published warehouse has none yet, so this source is
  empty until the team dimension is re-extracted.

`fetch_logos.py` skips any team that already has a file, so running it later
fills in the rest without touching these. `--force` there replaces them with
the source's own images.

## Refreshing them

```bash
python scripts/fetch_logos.py            # every team missing a file
python scripts/fetch_logos.py --force    # re-fetch what is already here
```

It reads `team_logo_url` from `marts.mart_team_season`, so it needs a warehouse
built from a live extract. The synthetic demo seasons carry no logo URLs at
all, and the script says so and exits rather than writing anything.

It is deliberately not in the nightly pipeline. A team's logo changes about as
often as its name, and re-fetching every image each night to find that out
would be rude to the host for no gain. Run it after a backfill rebuilds the
team dimension, or when a page shows initials where a logo belongs.

## What is in here

School logos are their owners' trademarks, mirrored for editorial use on a
non-commercial project that reports on their teams. They are not the lab's
work and are not covered by the repository's licence. A school that would
rather not appear here only has to say so: delete the file and the page draws
its initials instead, which is the same path every team without a logo already
takes.
