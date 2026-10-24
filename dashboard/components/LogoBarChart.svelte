<!--
  A BarChart whose team axis carries each team's logo beside its name.

  Everything is Evidence's own BarChart and every prop passes through. The
  addition is the category axis's labels: ECharts draws an image inside a
  label through a rich-text style whose background is that image, so each
  team with a logo gets a style of its own and the label names it. A team
  with no logo keeps a plain label.

  Like LogoScatter, nothing changes until the logo index has loaded in the
  browser, so the prerendered page is the ordinary chart.
-->
<script>
    import { BarChart } from '@evidence-dev/core-components';
    import { onMount } from 'svelte';
    import { logoIndex, loadLogoIndex } from './teamLogos.js';

    export let data;
    export let x;
    export let swapXY = false;
    export let logoSize = 16;

    onMount(loadLogoIndex);

    function labelOptions(index, rows) {
        if (!index || !index.size || !rows) return undefined;
        const keys = new Map();
        const rich = {};
        for (const row of rows) {
            const name = row?.[x];
            const url = index.get(name);
            if (!url || keys.has(name)) continue;
            const key = `logo${keys.size}`;
            keys.set(name, key);
            rich[key] = {
                width: logoSize,
                height: logoSize,
                backgroundColor: { image: url }
            };
        }
        if (!keys.size) return undefined;
        // The category axis is y when the bars run sideways.
        const axis = swapXY ? 'yAxis' : 'xAxis';
        return {
            [axis]: {
                axisLabel: {
                    formatter: (value) => (keys.has(value) ? `${value} {${keys.get(value)}|}` : value),
                    rich
                }
            }
        };
    }

    $: echartsOptions = labelOptions($logoIndex, data);
</script>

<BarChart {...$$restProps} {data} {x} {swapXY} {echartsOptions} />
