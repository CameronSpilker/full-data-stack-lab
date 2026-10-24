// The team-name -> logo index every logo on the dashboard reads.
//
// It is built in the browser from /logos/manifest.json, the file the logo
// import scripts write beside the images, rather than from a query, because
// it is about which files exist and a query cannot know that. A name is the
// key because that is what tables and chart tooltips already carry; the
// manifest records each team under the same `team_name` the marts use.
//
// Browser only, and loaded once. Nothing here runs while a page prerenders:
// SvelteKit's crawler follows any image path it finds in server-rendered
// markup and fails the build on the first one that is missing (see
// TeamCrest.svelte), so logos are always added after the page is up.
import { writable } from 'svelte/store';
import { addBasePath } from '@evidence-dev/sdk/utils/svelte';

/** Map of team name to logo URL, or null until the manifest has loaded. */
export const logoIndex = writable(null);

let requested = false;

export function loadLogoIndex() {
    if (requested || typeof window === 'undefined') return;
    requested = true;
    fetch(addBasePath('/logos/manifest.json'))
        .then((response) => (response.ok ? response.json() : {}))
        .then((manifest) => {
            const index = new Map();
            for (const [teamId, entry] of Object.entries(manifest)) {
                if (entry && entry.team_name) {
                    index.set(entry.team_name, addBasePath(`/logos/${teamId}.png`));
                }
            }
            logoIndex.set(index);
        })
        // No manifest means no logos, and every page reads as it did before.
        .catch(() => logoIndex.set(new Map()));
}
