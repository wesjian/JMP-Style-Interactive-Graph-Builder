/* Graph Builder canvas resize handler.
 * Uses ResizeObserver to trigger Plotly relayout when the user drags
 * the bottom-right resize handle of #gb-graph-resizer.
 *
 * Plotly.Plots.resize() updates the SVG width/height but does NOT re-run
 * the autoexpand margin / legend-position calculation. When the wrapper
 * is dragged narrower, a right-anchored legend (x=1.02) stays at its old
 * pixel offset and gets clipped by overflow:hidden. We follow up with
 * Plotly.relayout({autosize: true}) on a short debounce to force the
 * full layout recompute. */
(function() {
    var initialized = false;
    var resizeTimer = null;

    function relayout(wrapper) {
        var gd = wrapper.querySelector('.js-plotly-plot');
        if (!gd || !window.Plotly || typeof window.Plotly.Plots === 'undefined') return;
        // First pass: snap SVG to container size
        window.Plotly.Plots.resize(gd);
        // Second pass: force margin / legend autoexpand
        if (typeof window.Plotly.relayout === 'function') {
            window.Plotly.relayout(gd, {autosize: true}).catch(function() {});
        }
    }

    function initResize() {
        if (initialized) return;
        var wrapper = document.getElementById('gb-graph-resizer');
        if (!wrapper || !window.ResizeObserver) return;
        var ro = new ResizeObserver(function() {
            if (resizeTimer) clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function() { relayout(wrapper); }, 60);
        });
        ro.observe(wrapper);
        initialized = true;
    }

    // Try immediately, then poll a few times in case the layout mounts later
    document.addEventListener('DOMContentLoaded', initResize);
    var tries = 0;
    var iv = setInterval(function() {
        initResize();
        if (initialized || ++tries > 20) clearInterval(iv);
    }, 500);
})();
