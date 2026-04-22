// Alpine component for the Paperless Feeder UI.
//
// Registered via `alpine:init` so it's defined before Alpine scans the DOM.
// Referenced from the template with `x-data="documentUploader"`. Keeping
// the component in a named module (instead of inline `x-data="{...}"` on
// <body>) makes the scope explicit — every property here is clearly
// component-local, which is the distinction HTMX's `hx-vals="js:..."`
// forgets (and which broke submit-with-tag in commit 74fcbd6). See
// STANDARDS.md rule 5.

document.addEventListener('alpine:init', () => {
    Alpine.data('documentUploader', () => ({
        uploading: false,
        submitting: false,
        processing: 0,
        tagsLoaded: false,
        tagsError: false,
        tags: [],
        selectedTags: [],
        labelOpen: false,
        labelSearch: '',

        init() {
            this.loadTags();
            this.$nextTick(() => window.lucide && window.lucide.createIcons());
        },

        loadTags() {
            fetch('/tags')
                .then(r => {
                    if (!r.ok) throw new Error('tags ' + r.status);
                    return r.json();
                })
                .then(data => {
                    this.tags = data;
                    this.tagsLoaded = true;
                    this.$nextTick(() => window.lucide && window.lucide.createIcons());
                })
                .catch(() => { this.tagsError = true; });
        },

        toggleTag(id) {
            const i = this.selectedTags.indexOf(id);
            if (i === -1) this.selectedTags.push(id);
            else this.selectedTags.splice(i, 1);
        },

        filteredTags() {
            const q = this.labelSearch.trim().toLowerCase();
            if (!q) return this.tags;
            return this.tags.filter(t => t.name.toLowerCase().includes(q));
        },

        tagsParam() {
            return JSON.stringify({ tags: this.selectedTags });
        },
    }));
});
