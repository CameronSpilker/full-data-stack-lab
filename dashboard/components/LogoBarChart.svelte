<!--
  A BarChart whose team axis carries each team's logo beside its name.

  Everything is Evidence's own BarChart and every prop passes through. The
  addition is the category axis's labels: ECharts draws an image inside a
  label through a rich-text style whose background is that image, so each
  team with a logo gets a style of its own and the label names it. A team
  with no logo keeps a plain label.

  Like LogoScatter, nothing changes until the logo index has loaded in the
  browser, so the prerendered page is the ordinary chart.

  `colorColumn` draws each bar in its team's colour (six hex digits, as the
  warehouse stores it), for a chart of one series where colour only says
  which team. A colour too light to see against the page takes
  `altColorColumn`, the team's second colour, and the series colour if there
  is none.
-->
<script>
    import { BarChart } from '@evidence-dev/core-components';
    import { onMount } from 'svelte';
    import { logoIndex, loadLogoIndex } from './teamLogos.js';

    export let data;
    export let x;
    export let swapXY = false;
    export let logoSize = 16;
    export let colorColumn = undefined;
    export let altColorColumn = undefined;

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

    function luminance(hex) {
        const n = parseInt(hex, 16);
        return 0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255);
    }

    function teamColors(rows) {
        if (!colorColumn || !rows) return undefined;
        const colors = new Map();
        for (const row of rows) {
            const primary = row?.[colorColumn];
            const alternate = altColorColumn ? row?.[altColorColumn] : undefined;
            const ok = (hex) => typeof hex === 'string' && /^[0-9a-fA-F]{6}$/.test(hex);
            if (ok(primary) && luminance(primary) <= 215) colors.set(row[x], `#${primary}`);
            else if (ok(alternate)) colors.set(row[x], `#${alternate}`);
        }
        if (!colors.size) return undefined;
        return {
            itemStyle: {
                color: (params) => {
                    const category =
                        params.name ||
                        (Array.isArray(params.value) ? params.value[swapXY ? 1 : 0] : undefined);
                    // A team without a usable colour takes the palette's first
                    // hue, the one a single-series bar would have had.
                    return colors.get(category) ?? '#2a78d6';
                }
            }
        };
    }

    $: seriesOptions = teamColors(data);
</script>

<BarChart {...$$restProps} {data} {x} {swapXY} {echartsOptions} {seriesOptions} />
