<!--
  The row of view buttons that sits at the top of every page.

  Evidence builds its own sidebar from the pages directory, which is the right
  nav for someone who already knows the site. This is for someone who does
  not: the views are a small fixed set, they answer different questions about
  the same season, and the useful thing is to be able to step between them
  without going back to a menu.

  It also reaches the dbt Charts boards under /charts, which the sidebar cannot
  list at all. Those pages are static HTML unpacked into this site's static
  directory by the deploy script, so Evidence never sees them as routes. They
  are the second presentation layer over the same marts, and the banner is what
  makes the two feel like one site rather than two that happen to share a
  domain.

  `current` is the slug of the page drawing it. That entry renders as text
  rather than as a link, because a link to the page you are already on is a
  dead control that costs a reader a click to discover.
-->
<script>
    export let current = '';

    /** The whole of the site's navigation, in one list.
     *
     *  The boards are named by absolute URL, which is the same way
     *  how-it-works already links to them, and it is not a style choice. The
     *  boards are an optional release asset: `scripts/fetch-warehouse.sh`
     *  unpacks them when the release has them and says so when it does not,
     *  and the dashboard is still a dashboard either way. A site-relative
     *  /charts/ makes that optional thing mandatory, because SvelteKit's
     *  prerenderer crawls every internal link it finds and fails the whole
     *  build on one that 404s. An off-origin URL is not crawled, so a missing
     *  board costs a reader one dead link instead of costing everyone the
     *  site.
     *
     *  `rel="external"` on top of that keeps the client router from trying to
     *  resolve it as a route.
     */
    const BOARDS = 'https://lab.cameronspilker.com/charts/';
    const views = [
        { slug: 'index', label: 'Overview', href: '/' },
        { slug: 'rankings', label: 'Rankings', href: '/rankings' },
        { slug: 'scorecard', label: 'Scorecard', href: '/scorecard' },
        { slug: 'matchup', label: 'Matchup', href: '/matchup' },
        { slug: 'picks', label: 'Picks', href: '/picks' },
        { slug: 'bracket', label: 'Bracket', href: '/bracket' },
        { slug: 'conferences', label: 'Conferences', href: '/conferences' },
        { slug: 'model', label: 'Model', href: '/model' },
        { slug: 'charts', label: 'Charts', href: BOARDS, external: true },
    ];
</script>

<nav class="view-nav" aria-label="Views">
    {#each views as view (view.slug)}
        {#if view.slug === current}
            <span class="view is-current" aria-current="page">{view.label}</span>
        {:else if view.external}
            <a class="view" href={view.href} rel="external">{view.label}</a>
        {:else}
            <a class="view" href={view.href}>{view.label}</a>
        {/if}
    {/each}
</nav>

<style>
    /* Colours are derived from `currentColor` rather than named, so the row
       follows the reader's appearance without a hex being written twice. This
       is the same rule the AwaitingData placeholder follows. */
    .view-nav {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin: 0 0 1.5rem;
        padding: 0;
    }

    .view {
        padding: 0.3rem 0.7rem;
        border: 1px solid color-mix(in srgb, currentColor 18%, transparent);
        border-radius: 0.375rem;
        background: color-mix(in srgb, currentColor 3%, transparent);
        font-size: 0.8rem;
        line-height: 1.4;
        text-decoration: none;
        color: inherit;
        white-space: nowrap;
    }

    a.view:hover {
        border-color: color-mix(in srgb, currentColor 38%, transparent);
        background: color-mix(in srgb, currentColor 8%, transparent);
    }

    /* The current view reads as pressed rather than as a link. */
    .is-current {
        border-color: color-mix(in srgb, currentColor 45%, transparent);
        background: color-mix(in srgb, currentColor 12%, transparent);
        font-weight: 600;
    }

    /* Keyboard focus has to stay visible: the buttons are small, and losing
       the ring on a wrapped row makes the whole banner unusable without a
       mouse. */
    a.view:focus-visible {
        outline: 2px solid currentColor;
        outline-offset: 2px;
    }
</style>
