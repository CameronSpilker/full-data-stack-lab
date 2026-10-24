"""The live scorecard and matchup boards, as a Vercel Function.

The published boards under /charts are static HTML, and a static page cannot
keep dbt Charts' team pickers. These two boards are the exception: this
function runs dbt Charts' own server (what `dct serve` runs locally) so the
pickers work, and the dashboard's vercel.json sends /charts/scorecard/ and
/charts/matchup/ here.

Only those two boards are answered. Everything else the server can do (the
table inspector, the live-reload stream, the other boards, the template
listing) is a local authoring tool, so it returns 404 here.

The warehouse is not in git. The function downloads the copy the nightly
pipeline publishes on its first request, into /tmp (the only writable place
in a function), and fetches it again once it is more than a few hours old, so
a long-lived instance does not keep serving last week's numbers.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
import urllib.parse
import urllib.request
from contextlib import AsyncExitStack
from pathlib import Path

from starlette.responses import PlainTextResponse

REPO = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("LIVE_WORKDIR", "/tmp/live-charts"))
WAREHOUSE_URL = os.environ.get(
    "WAREHOUSE_URL",
    "https://github.com/CameronSpilker/full-data-stack-lab/releases/download/"
    "warehouse-latest/warehouse.duckdb",
)
# How old the local copy may get before the next request fetches it again.
WAREHOUSE_MAX_AGE = 6 * 60 * 60
# How long the CDN may serve a drawn page before asking again. Every board
# reads one warehouse that changes once a night, so an hour costs nothing in
# freshness and spares most visits a two-second render.
CDN_CACHE = "public, max-age=0, s-maxage=3600, stale-while-revalidate=86400"

BOARDS = ("scorecard", "matchup")
# The same additions scripts/render-charts.sh makes to the static pages (the
# scoreboard face and the team logos), plus one more: the server's own top bar
# (breadcrumb, data and download menus) links to routes this function does not
# answer, so it is hidden. The team pickers sit outside it and stay.
HEAD_EXTRA = (REPO / "scripts" / "charts-head.html").read_text(encoding="utf-8") + (
    '<style id="live-boards">.dbt-nav{display:none !important;}</style>'
)

_lock = threading.Lock()
_server = None
_running: AsyncExitStack | None = None
_fetched_at = 0.0


def _stage() -> None:
    """Lay the project out under /tmp with a fresh warehouse beside it.

    dbt Charts reads boards, templates and dbt_charts.yml from one project
    root, and the warehouse path in dbt_charts.yml is relative to it. The
    deployed source is read-only, so the root is a copy in /tmp.
    """
    global _fetched_at
    (WORK / "data").mkdir(parents=True, exist_ok=True)
    for name in ("charts", "templates"):
        target = WORK / name
        if not target.exists():
            shutil.copytree(REPO / name, target)
    shutil.copyfile(REPO / "dbt_charts.yml", WORK / "dbt_charts.yml")

    partial = WORK / "data" / "warehouse.duckdb.part"
    urllib.request.urlretrieve(WAREHOUSE_URL, partial)
    partial.replace(WORK / "data" / "warehouse.duckdb")
    _fetched_at = time.time()


async def _board_server():
    """dbt Charts' server for the staged project, built once per instance.

    Its startup work (opening the warehouse, building the adapter registry)
    runs in its lifespan, which is entered here and held open until the
    warehouse is refreshed and the server rebuilt.
    """
    global _server, _running
    stale = time.time() - _fetched_at > WAREHOUSE_MAX_AGE
    if _server is not None and not stale:
        return _server
    with _lock:
        if _running is not None:
            await _running.aclose()
            _running = None
        _stage()
        from dbt_charts.cli.filesystem_project import FilesystemProject
        from dbt_charts.core.serve.server import create_server

        # No query cache: the default one lives in the home directory, which
        # a function cannot write to, and the CDN cache in front of this
        # does the same job.
        server = create_server(FilesystemProject(WORK), dialect="duckdb", no_cache=True)
        running = AsyncExitStack()
        await running.enter_async_context(server.router.lifespan_context(server))
        _server, _running = server, running
        return _server


def _board_of(path: str) -> str | None:
    parts = [p for p in path.split("/") if p]
    # Reached through the dashboard's rewrite as /charts/<board>/, or
    # directly on this project's own URL as /<board>/.
    if parts[:1] == ["charts"]:
        parts = parts[1:]
    return parts[0] if len(parts) == 1 and parts[0] in BOARDS else None


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        # dbt Charts' lifespan runs once the server exists, on first request.
        message = await receive()
        while message["type"] != "lifespan.shutdown":
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            message = await receive()
        await send({"type": "lifespan.shutdown.complete"})
        return
    if scope["type"] != "http":
        return

    # vercel.json sends every path here as /api/index?__path=<original>. Read
    # the board from that and keep the rest of the query (the team picks).
    path = scope["path"]
    query = urllib.parse.parse_qsl(scope.get("query_string", b"").decode(), keep_blank_values=True)
    original = [v for k, v in query if k == "__path"]
    if original:
        path = original[0]
        query = [(k, v) for k, v in query if k != "__path"]
    board = _board_of(path)
    if board is None or scope["method"] not in ("GET", "HEAD"):
        await PlainTextResponse("Not found", status_code=404)(scope, receive, send)
        return

    server = await _board_server()
    inner = dict(
        scope,
        path=f"/{board}/",
        raw_path=f"/{board}/".encode(),
        query_string=urllib.parse.urlencode(query).encode(),
    )

    start: dict = {}
    body = bytearray()

    async def capture(message):
        if message["type"] == "http.response.start":
            start.update(message)
        elif message["type"] == "http.response.body":
            body.extend(message.get("body", b""))

    await server(inner, receive, capture)

    headers = [
        (k, v)
        for k, v in start.get("headers", [])
        if k.lower() not in (b"content-length", b"cache-control")
    ]
    content = bytes(body)
    status = start.get("status", 500)
    is_html = any(k.lower() == b"content-type" and b"text/html" in v for k, v in headers)
    if is_html and status == 200:
        content = (
            content.decode("utf-8").replace("</head>", HEAD_EXTRA + "</head>", 1).encode("utf-8")
        )
        headers.append((b"cache-control", CDN_CACHE.encode()))
    else:
        headers.append((b"cache-control", b"no-store"))
    headers.append((b"content-length", str(len(content)).encode()))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": content})
