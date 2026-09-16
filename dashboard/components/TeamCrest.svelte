<!--
  A team's logo, or its initials when there is no logo to draw.

  The logos are mirrored into this site's own static files by
  `scripts/fetch_logos.py`, under one rule rather than a lookup table: a team
  with a mirrored logo has it at /logos/<team_id>.png. So this builds the path
  from the id the page already has, and never needs the manifest.

  The initials are what this renders, and the logo is an upgrade applied in the
  browser. That order is deliberate and it is not only about taste.

  The mirror is allowed to be partial: a team can have no logo upstream, the
  synthetic demo seasons have none at all, and a file can be removed at a
  school's request. But SvelteKit prerenders these pages, and its crawler
  follows an `img src` exactly as it follows a link, so a `src` written into
  the server-rendered markup makes the build fail on the first team whose file
  is not there. An `on:error` handler does not save it: the handler runs in a
  browser, and the build has already stopped. That is a real failure, not a
  hypothetical one, and it took the whole site down until this was inverted.

  So the path is never in the markup the build sees. On mount the browser
  probes the file, and the image replaces the initials only once it has
  actually loaded. A missing logo is then invisible: no broken image, no
  layout shift, and no bearing at all on whether the site builds.

  `color` tints the initials with the team's own colour where the warehouse
  has one. It is used only here, on a team's own crest, and never in a chart:
  chart colour comes from the validated categorical palette, which is chosen
  for separation rather than for whose colours they are.
-->
<script>
    import { addBasePath } from '@evidence-dev/sdk/utils/svelte';
    import { onMount } from 'svelte';

    export let teamId = '';
    export let name = '';
    /** Six hex digits with no leading "#", as the warehouse stores it. */
    export let color = '';
    export let size = 44;

    /** The path, once a browser has confirmed the file is really there. */
    let resolved = '';
    let mounted = false;

    onMount(() => {
        mounted = true;
    });

    /** Ask the browser whether this team has a mirrored logo.
     *
     *  Re-runs whenever the id changes, which is what happens on every
     *  dropdown change, so one team's missing logo cannot leave the next
     *  team's crest empty. The id is checked again on the callback because a
     *  reader can change the pick before a slow response lands, and the late
     *  answer to the old question must not overwrite the new one.
     */
    function probe(id) {
        resolved = '';
        if (!id) return;

        // The dashboard is served under /evidence, so the path takes the
        // configured base rather than assuming the site root.
        const candidate = addBasePath(`/logos/${id}.png`);
        const image = new Image();
        image.onload = () => {
            if (teamId === id) resolved = candidate;
        };
        image.src = candidate;
    }

    // Guarded on `mounted` so it never runs while the page is being
    // prerendered, where there is no Image and nothing to ask.
    $: if (mounted) probe(teamId);

    /** Up to three letters, from the words a reader would say. */
    $: initials = (name || '')
        .split(/\s+/)
        .filter((word) => /^[A-Za-z]/.test(word))
        .slice(0, 3)
        .map((word) => word[0].toUpperCase())
        .join('');

    $: tint = /^[0-9A-Fa-f]{6}$/.test(color || '') ? `#${color}` : null;
</script>

<div class="crest" style="width: {size}px; height: {size}px">
    {#if resolved}
        <img src={resolved} alt="" width={size} height={size} />
    {:else}
        <span
            class="initials"
            style:background={tint
                ? `color-mix(in srgb, ${tint} 16%, transparent)`
                : null}
            style:color={tint}
            style:font-size="{Math.round(size * 0.36)}px"
            aria-hidden="true"
        >{initials}</span>
    {/if}
</div>

<style>
    .crest {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex: none;
    }

    .crest img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }

    /* Derived from `currentColor` when the team has no colour of its own, so
       the fallback follows the reader's appearance rather than naming a hex. */
    .initials {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        height: 100%;
        border-radius: 0.375rem;
        background: color-mix(in srgb, currentColor 10%, transparent);
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
</style>
