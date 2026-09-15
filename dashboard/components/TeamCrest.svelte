<!--
  A team's logo, or its initials when there is no logo to draw.

  The logos are mirrored into this site's own static files by
  `scripts/fetch_logos.py`, under one rule rather than a lookup table: a team
  with a mirrored logo has it at /logos/<team_id>.png. So this builds the path
  from the id the page already has, and never needs the manifest.

  The fallback is the point. The mirror is allowed to be partial: a team can
  have no logo upstream, the synthetic demo seasons have none at all, and a
  file can be removed at a school's request. None of those should put a
  broken image beside a number. An image that fails to load swaps itself for
  the team's initials on its own `error` event, which also covers the case the
  build cannot see: a file that was in static/ at build time and is not there
  now.

  `color` tints the initials with the team's own colour where the warehouse
  has one. It is used only here, on a team's own crest, and never in a chart:
  chart colour comes from the validated categorical palette, which is chosen
  for separation rather than for whose colours they are.
-->
<script>
    export let teamId = '';
    export let name = '';
    /** Six hex digits with no leading "#", as the warehouse stores it. */
    export let color = '';
    export let size = 44;

    let failed = false;

    // Reset when the component is reused for a different team, which is what
    // happens on every dropdown change: without this, one team's missing logo
    // would leave the next team's crest showing initials.
    $: if (teamId) {
        failed = false;
    }

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
    {#if teamId && !failed}
        <img
            src="/logos/{teamId}.png"
            alt=""
            width={size}
            height={size}
            loading="lazy"
            on:error={() => (failed = true)}
        />
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
