<!--
  Evidence's default layout, plus team logos in every table.

  Any table cell whose text is exactly a team's name gets that team's logo in
  front of it. It is done here, once, rather than with an image column on each
  DataTable, for two reasons. Every table that names a team gets it, including
  ones added later, with no page needing to know. And it happens in the
  browser after the page is up: an image path in prerendered markup is
  something SvelteKit's crawler follows, and one missing file fails the whole
  build (see components/TeamCrest.svelte).

  Tables sort, search and paginate by re-rendering their rows, so a
  MutationObserver re-applies the logos to whatever is on screen. A cell that
  already has one is left alone, which is also what stops the observer from
  reacting to its own changes.
-->
<script>
    import '@evidence-dev/tailwind/fonts.css';
    import '../app.css';
    import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
    import { onMount } from 'svelte';
    import { logoIndex, loadLogoIndex } from '../components/teamLogos.js';
    export let data;

    const LOGO = 'team-logo';

    function decorate(index, root) {
        for (const cell of root.querySelectorAll('td')) {
            if (cell.querySelector(`img.${LOGO}`)) continue;
            const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
            for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                const name = node.nodeValue.trim();
                const url = name && index.get(name);
                if (!url) continue;
                const img = document.createElement('img');
                img.className = LOGO;
                img.src = url;
                img.alt = '';
                img.width = 18;
                img.height = 18;
                img.loading = 'lazy';
                // A file that fails to load takes its image with it, so the
                // cell reads exactly as it did without one.
                img.onerror = () => img.remove();
                node.parentNode.insertBefore(img, node);
                break;
            }
        }
    }

    onMount(() => {
        loadLogoIndex();
        let observer;
        let queued = false;
        const unsubscribe = logoIndex.subscribe((index) => {
            if (!index || !index.size || observer) return;
            decorate(index, document.body);
            observer = new MutationObserver(() => {
                if (queued) return;
                queued = true;
                requestAnimationFrame(() => {
                    queued = false;
                    decorate(index, document.body);
                });
            });
            observer.observe(document.body, { childList: true, subtree: true });
        });
        return () => {
            unsubscribe();
            observer?.disconnect();
        };
    });
</script>

<EvidenceDefaultLayout {data}>
    <slot slot="content" />
</EvidenceDefaultLayout>

<style>
    :global(img.team-logo) {
        display: inline-block;
        width: 18px;
        height: 18px;
        object-fit: contain;
        vertical-align: -4px;
        margin-right: 6px;
    }
</style>
