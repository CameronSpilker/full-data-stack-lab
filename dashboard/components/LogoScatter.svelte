<!--
  A ScatterPlot that draws each team as its logo.

  Everything is Evidence's own ScatterPlot (axes, tooltip, legend, colours,
  the inverted defence axis) and every prop passes straight through. The one
  addition is a point symbol: ECharts takes `symbol` as a function of the
  point, and with `tooltipTitle` set the third value of each point is the
  team's name, which is what the logo index is keyed on. A team with no logo
  keeps the plain dot in its series colour, so the series still reads.

  The symbol only arrives once the logo index has loaded in the browser, so
  the prerendered page and a reader with no logos both get the ordinary
  chart, and nothing here can affect the build.

  `highlight` names one team to draw larger, for a page about that team.
-->
<script>
    import { ScatterPlot } from '@evidence-dev/core-components';
    import { onMount } from 'svelte';
    import { logoIndex, loadLogoIndex } from './teamLogos.js';

    export let logoSize = 18;
    export let highlight = undefined;

    onMount(loadLogoIndex);

    $: seriesOptions =
        $logoIndex && $logoIndex.size
            ? {
                  symbol: (value) => {
                      const url = $logoIndex.get(value?.[2]);
                      return url ? `image://${url}` : 'circle';
                  },
                  symbolSize: (value) => {
                      const big = highlight && value?.[2] === highlight;
                      const size = $logoIndex.has(value?.[2]) ? logoSize : logoSize * 0.5;
                      return big ? size * 2 : size;
                  },
                  itemStyle: { opacity: 1, borderWidth: 0 }
              }
            : undefined;
</script>

<ScatterPlot {...$$restProps} {seriesOptions} />
