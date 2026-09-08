<!--
  The slot a chart or a table will occupy once there is something to draw in it.

  Most of this site is built from results, and for about seven months of the
  year some of it has none: the season ends in April, the next schedule is not
  published until the autumn, and in between the forecast has nothing to price.
  An empty chart in that window is indistinguishable from a broken one. This
  says which visual is missing, why, and what makes it come back, and it is
  always rendered from a check on the data rather than from a date, so the page
  swaps back to the real chart the run after the rows arrive.

  `title` names the visual that belongs here, so the placeholder reads as a
  labelled gap rather than an error. `detail` is the reason, in a sentence.
-->
<script>
    export let title = '';
    export let detail = '';
    /** Roughly the height of the chart being stood in for, so the page does not
        reflow when the data lands. */
    export let height = 220;
</script>

<figure class="awaiting" style="min-height: {height}px">
    <figcaption class="awaiting-label">Waiting on data</figcaption>
    {#if title}
        <p class="awaiting-title">{title}</p>
    {/if}
    {#if detail}
        <p class="awaiting-detail">{detail}</p>
    {/if}
    <slot />
</figure>

<style>
    /* Everything here is derived from `currentColor`, so the placeholder picks
       up whichever appearance the reader is in without naming a hex twice. */
    .awaiting {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 0.35rem;
        margin: 1rem 0;
        padding: 1.25rem;
        border: 1px dashed color-mix(in srgb, currentColor 28%, transparent);
        border-radius: 0.375rem;
        background: color-mix(in srgb, currentColor 3%, transparent);
    }

    .awaiting-label {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 0.7rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        opacity: 0.55;
    }

    .awaiting-title {
        margin: 0;
        font-size: 0.95rem;
        font-weight: 500;
    }

    .awaiting-detail {
        margin: 0;
        max-width: 60ch;
        font-size: 0.85rem;
        line-height: 1.5;
        opacity: 0.75;
    }
</style>
