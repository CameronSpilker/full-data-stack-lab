<!--
  The top bar of view buttons on every Evidence page.

  Evidence builds its own sidebar from the pages directory, which suits a
  reader who already knows the site. This bar is for one who does not: the
  views are a small fixed set, and the useful thing is to step between them
  without going back to a menu.

  The dashboard stands on its own. It is served under /evidence, and nothing
  here points outside it: the dbt Charts boards are a separate site with a
  bar of their own.

  Every href goes through addBasePath. Evidence only rewrites literal hrefs
  in page markdown, so a path built in a component would otherwise skip the
  /evidence prefix and send the reader to the landing page instead.

  `current` is the slug of the page drawing it. That entry is filled in and
  rendered as text, because a link to the page you are already on is a dead
  control.
-->
<script>
    import { addBasePath } from '@evidence-dev/sdk/utils/svelte';

    export let current = '';

    const views = [
        { slug: 'index', label: 'Overview', href: '/' },
        { slug: 'rankings', label: 'Rankings', href: '/rankings' },
        { slug: 'scorecard', label: 'Scorecard', href: '/scorecard' },
        { slug: 'matchup', label: 'Matchup', href: '/matchup' },
        { slug: 'picks', label: 'Picks', href: '/picks' },
        { slug: 'bracket', label: 'Bracket', href: '/bracket' },
        { slug: 'conferences', label: 'Conferences', href: '/conferences' },
        { slug: 'model', label: 'Model', href: '/model' },
        { slug: 'how-it-works', label: 'How it works', href: '/how-it-works' },
    ];
</script>

<nav class="view-nav" aria-label="Dashboard views">
    <ul>
        {#each views as view (view.slug)}
            <li>
                {#if view.slug === current}
                    <span class="view is-current" aria-current="page">{view.label}</span>
                {:else}
                    <a class="view" href={addBasePath(view.href)}>{view.label}</a>
                {/if}
            </li>
        {/each}
    </ul>
</nav>

<style>
    /* One bar, not a row of loose links: a raised strip holding equal
       buttons. The colours are the theme's own variables, so the bar follows
       light and dark without a hex written here. */
    .view-nav {
        margin: 0 0 1.75rem;
        padding: 0.3rem;
        border: 1px solid var(--base-300);
        border-radius: 0.6rem;
        background: var(--base-200);
        /* On a narrow screen the bar scrolls sideways instead of wrapping
           into a ragged second row. */
        overflow-x: auto;
        scrollbar-width: none;
    }

    .view-nav::-webkit-scrollbar {
        display: none;
    }

    ul {
        display: flex;
        gap: 0.25rem;
        margin: 0;
        padding: 0;
        list-style: none;
    }

    li {
        flex: 1 0 auto;
        margin: 0;
    }

    .view {
        display: block;
        padding: 0.45rem 0.85rem;
        border-radius: 0.4rem;
        font-size: 0.82rem;
        font-weight: 500;
        line-height: 1.3;
        text-align: center;
        text-decoration: none;
        white-space: nowrap;
        color: var(--base-content);
        transition:
            background-color 120ms ease,
            color 120ms ease;
    }

    a.view:hover {
        background: var(--base-100);
        color: var(--base-heading);
        box-shadow: 0 1px 2px color-mix(in srgb, var(--base-heading) 10%, transparent);
    }

    .is-current {
        background: var(--primary);
        color: #fff;
        font-weight: 600;
    }

    a.view:focus-visible {
        outline: 2px solid var(--primary);
        outline-offset: 1px;
    }
</style>
