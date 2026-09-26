// JMP-style Graph Builder - Full Drag & Drop + Icon Button Engine
(function() {
    'use strict';

    var ZONE_MAP = {
        'gb-drop-x':       {dropdown: 'gb-x-axis', multi: false},
        'gb-drop-y':       {dropdown: 'gb-y-axis', multi: true, max: 6},
        'gb-drop-y2':      {dropdown: 'gb-y2-axis', multi: true},
        'gb-drop-color':   {dropdown: 'gb-color', multi: false},
        'gb-drop-size':    {dropdown: 'gb-size', multi: false},
        'gb-drop-group-x': {dropdown: 'gb-group-x', multi: false},
        'gb-drop-group-y': {dropdown: 'gb-group-y', multi: false},
    };

    // Chart type button -> hidden dropdown value mapping
    var TYPE_BUTTONS = {
        'gb-type-scatter': 'scatter', 'gb-type-line': 'line', 'gb-type-bar': 'bar',
        'gb-type-box': 'box', 'gb-type-histogram': 'histogram', 'gb-type-violin': 'violin',
        'gb-type-bubble': 'bubble', 'gb-type-heatmap': 'heatmap', 'gb-type-pareto': 'pareto',
        'gb-type-correlation': 'correlation'
    };
    var FIT_BUTTONS = {
        'gb-fit-none': 'none', 'gb-fit-ols': 'ols', 'gb-fit-rolling': 'rolling', 'gb-fit-lowess': 'lowess', 'gb-fit-fcst': 'forecast'
    };
    var DG_BUTTONS = {
        'gb-dg-none': 'none', 'gb-dg-w': 'W', 'gb-dg-m': 'M', 'gb-dg-q': 'Q'
    };

    var _initTimer = null;
    var _lastInitCount = 0;
    var _reverseSync = false;  // flag to prevent re-syncing during reverse sync

    // ── Drag & Drop ──
    function initDragDrop() {
        var chips = document.querySelectorAll('.gb-drag-chip');
        if (!chips.length) return;
        if (chips.length === _lastInitCount) return;
        _lastInitCount = chips.length;

        chips.forEach(function(chip) {
            if (chip._dndBound) return;
            chip._dndBound = true;
            chip.setAttribute('draggable', 'true');
            chip.addEventListener('dragstart', function(e) {
                this.classList.add('dragging');
                e.dataTransfer.setData('text/plain', this.getAttribute('data-var'));
                e.dataTransfer.effectAllowed = 'copy';
            });
            chip.addEventListener('dragend', function() {
                this.classList.remove('dragging');
            });
            chip.addEventListener('dblclick', function() {
                addVarToZone('gb-drop-y', this.getAttribute('data-var'));
            });
        });

        document.querySelectorAll('.gb-drop-zone').forEach(function(zone) {
            if (zone._dndBound) return;
            zone._dndBound = true;
            zone.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'copy';
                this.classList.add('drag-over');
            });
            zone.addEventListener('dragleave', function(e) {
                if (!this.contains(e.relatedTarget)) this.classList.remove('drag-over');
            });
            zone.addEventListener('drop', function(e) {
                e.preventDefault();
                this.classList.remove('drag-over');
                var varName = e.dataTransfer.getData('text/plain');
                if (varName) addVarToZone(this.id, varName);
            });
        });

        // ── Icon Buttons for chart type / trend / date group ──
        setupButtonGroup(TYPE_BUTTONS, 'gb-chart-type', '#005baa');
        setupButtonGroup(FIT_BUTTONS, 'gb-trendline', '#7B1FA2');
        setupButtonGroup(DG_BUTTONS, 'gb-date-group', '#E65100');
    }

    function setupButtonGroup(buttonMap, dropdownId, activeColor) {
        Object.keys(buttonMap).forEach(function(btnId) {
            var btn = document.getElementById(btnId);
            if (!btn || btn._gbBound) return;
            btn._gbBound = true;
            btn.addEventListener('click', function() {
                setDashDropdownValue(dropdownId, buttonMap[btnId]);
                // Highlight active button
                Object.keys(buttonMap).forEach(function(id) {
                    var b = document.getElementById(id);
                    if (b) {
                        b.style.backgroundColor = (id === btnId) ? activeColor : '#fff';
                        b.style.color = (id === btnId) ? '#fff' : '#333';
                        b.style.borderColor = (id === btnId) ? activeColor : '#e2e8f0';
                    }
                });
            });
        });
        // Set initial active state (first button)
        var firstId = Object.keys(buttonMap)[0];
        var firstBtn = document.getElementById(firstId);
        if (firstBtn && !firstBtn._initStyled) {
            firstBtn._initStyled = true;
            firstBtn.style.backgroundColor = activeColor;
            firstBtn.style.color = '#fff';
            firstBtn.style.borderColor = activeColor;
        }
    }

    function triggerDashButton(btnId) {
        var el = document.getElementById(btnId);
        if (!el) return;
        var keys = Object.keys(el);
        var reactKey = null;
        for (var i = 0; i < keys.length; i++) {
            if (keys[i].indexOf('__reactFiber$') === 0 || keys[i].indexOf('__reactInternalInstance$') === 0) {
                reactKey = keys[i]; break;
            }
        }
        if (!reactKey) return;
        var fiber = el[reactKey];
        while (fiber) {
            if (fiber.memoizedProps && typeof fiber.memoizedProps.setProps === 'function') {
                var currentClicks = fiber.memoizedProps.n_clicks || 0;
                fiber.memoizedProps.setProps({n_clicks: currentClicks + 1});
                return;
            }
            fiber = fiber['return'];
        }
    }

    function addVarToZone(zoneId, varName) {
        var zone = document.getElementById(zoneId);
        var config = ZONE_MAP[zoneId];
        if (!zone || !config || !varName) return;

        // Hide placeholder
        var ph = zone.querySelector('.gb-zone-placeholder');
        if (ph) ph.style.display = 'none';

        var existing = zone.querySelectorAll('.gb-zone-chip');
        for (var i = 0; i < existing.length; i++) {
            if (existing[i].getAttribute('data-var') === varName) return;
        }
        if (!config.multi) existing.forEach(function(c) { c.remove(); });
        if (config.max && existing.length >= config.max) return;

        var chip = document.createElement('div');
        chip.className = 'gb-zone-chip';
        chip.setAttribute('data-var', varName);
        chip.innerHTML = '<span>' + varName + '</span><span class="chip-remove">&times;</span>';
        chip.querySelector('.chip-remove').addEventListener('click', function() {
            chip.remove();
            syncZoneToDropdown(zoneId);
            // Show placeholder if empty
            if (!zone.querySelector('.gb-zone-chip')) {
                var p = zone.querySelector('.gb-zone-placeholder');
                if (p) p.style.display = '';
            }
        });
        chip.setAttribute('draggable', 'true');
        chip.addEventListener('dragstart', function(e) {
            e.dataTransfer.setData('text/plain', varName);
            setTimeout(function() {
                chip.remove();
                syncZoneToDropdown(zoneId);
                if (!zone.querySelector('.gb-zone-chip')) {
                    var p = zone.querySelector('.gb-zone-placeholder');
                    if (p) p.style.display = '';
                }
            }, 50);
        });
        zone.appendChild(chip);
        syncZoneToDropdown(zoneId);
    }

    var _autoBuildTimer = null;
    var AUTO_BUILD_DELAY = 500; // 0.5 second debounce

    function triggerAutoBuild() {
        if (_autoBuildTimer) clearTimeout(_autoBuildTimer);
        _autoBuildTimer = setTimeout(function() {
            var buildBtn = document.getElementById('gb-btn-build');
            if (buildBtn) {
                // Only auto-build if we have at least X and Y filled
                var xZone = document.getElementById('gb-drop-x');
                var yZone = document.getElementById('gb-drop-y');
                var hasX = xZone && xZone.querySelector('.gb-zone-chip');
                var hasY = yZone && yZone.querySelector('.gb-zone-chip');
                if (hasX && hasY) {
                    buildBtn.click();
                }
            }
        }, AUTO_BUILD_DELAY);
    }

    function syncZoneToDropdown(zoneId) {
        if (_reverseSync) return;  // don't write back during reverse sync
        var zone = document.getElementById(zoneId);
        var config = ZONE_MAP[zoneId];
        if (!zone || !config) return;

        var values = [];
        zone.querySelectorAll('.gb-zone-chip').forEach(function(c) {
            values.push(c.getAttribute('data-var'));
        });
        setDashDropdownValue(config.dropdown, config.multi ? values : (values[0] || null));
        // Trigger debounced auto-build
        triggerAutoBuild();
    }
    function setDashDropdownValue(dropdownId, value) {
        var el = document.getElementById(dropdownId);
        if (!el) return;
        var keys = Object.keys(el);
        var reactKey = null;
        for (var i = 0; i < keys.length; i++) {
            if (keys[i].indexOf('__reactFiber$') === 0 || keys[i].indexOf('__reactInternalInstance$') === 0) {
                reactKey = keys[i]; break;
            }
        }
        if (!reactKey) return;
        var fiber = el[reactKey];
        while (fiber) {
            if (fiber.memoizedProps && typeof fiber.memoizedProps.setProps === 'function') {
                fiber.memoizedProps.setProps({value: value});
                return;
            }
            fiber = fiber['return'];
        }
    }

    // Debounced observer (only on graph builder page)
    var observer = new MutationObserver(function() {
        if (_initTimer) clearTimeout(_initTimer);
        _initTimer = setTimeout(initDragDrop, 400);
    });

    function fireDashInput(id) {
        var el = document.getElementById(id);
        if(!el) return;
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        // set random string to ensure "value" always triggers a dash callback
        nativeInputValueSetter.call(el, Date.now().toString());
        el.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // Handle Axis Clicks to show Popup (JMP-style)
    document.addEventListener('click', function(e) {
        // Find if we clicked on an X or Y axis element in Plotly
        var target = e.target;
        var yAxisClicked = false;
        var xAxisClicked = false;
        
        while (target && target !== document.body) {
            if (target.classList && (target.classList.contains('ytick') || target.classList.contains('g-ytitle'))) {
                yAxisClicked = true;
                break;
            }
            if (target.classList && (target.classList.contains('xtick') || target.classList.contains('g-xtitle'))) {
                xAxisClicked = true;
                break;
            }
            target = target.parentNode;
        }

        if (yAxisClicked) {
            fireDashInput('gb-btn-axis-y');
        } else if (xAxisClicked) {
            fireDashInput('gb-btn-axis-x');
        }
    }, true); // Use capture phase because Plotly may stop propagation

    // Handle general interaction (Time buttons, Specs, etc) for Auto Build
    document.addEventListener('click', function(e) {
        if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') {
            if (e.target.closest('#gb-controls-bar') || e.target.closest('#gb-chart-toolbar') || e.target.closest('.gb-palette-sidebar') || e.target.id === 'gb-add-filter' || e.target.closest('#gb-filter-container') || e.target.id === 'gb-axis-modal-apply') {
                // Ignore the build button itself and the action buttons
                var id = e.target.id || '';
                if (id !== 'gb-btn-build' && id !== 'gb-btn-done' && id !== 'gb-btn-edit') {
                    // For the apply button, we need slightly longer because we must wait for dash to update the config store first
                    if (id === 'gb-axis-modal-apply') {
                        clearTimeout(_autoBuildTimer);
                        _autoBuildTimer = setTimeout(function() {
                            var buildBtn = document.getElementById('gb-btn-build');
                            if (buildBtn) buildBtn.click();
                        }, 800);
                    } else {
                        triggerAutoBuild();
                    }
                }
            }
        }
    });

    document.addEventListener('change', function(e) {
        if (e.target.closest('#gb-controls-bar') || e.target.closest('#gb-chart-toolbar') || e.target.closest('.gb-palette-sidebar') || e.target.closest('#gb-filter-container')) {
            triggerAutoBuild();
        }
    }, true);

    // ── Reverse sync: Dropdown values → Zone chips (for URL restore) ──
    function syncDropdownsToZones() {
        Object.keys(ZONE_MAP).forEach(function(zoneId) {
            var config = ZONE_MAP[zoneId];
            var zone = document.getElementById(zoneId);
            var dd = document.getElementById(config.dropdown);
            if (!zone || !dd) return;

            // Read current dropdown value from Dash's internal state
            var keys = Object.keys(dd);
            var reactKey = null;
            for (var i = 0; i < keys.length; i++) {
                if (keys[i].indexOf('__reactFiber$') === 0 || keys[i].indexOf('__reactInternalInstance$') === 0) {
                    reactKey = keys[i]; break;
                }
            }
            if (!reactKey) return;
            var fiber = dd[reactKey];
            var val = null;
            while (fiber) {
                if (fiber.memoizedProps && fiber.memoizedProps.value !== undefined) {
                    val = fiber.memoizedProps.value;
                    break;
                }
                fiber = fiber['return'];
            }
            if (!val) return;

            var values = Array.isArray(val) ? val : [val];
            // Extract string values — Dash may store {label, value} objects
            values = values.map(function(v) {
                if (v && typeof v === 'object' && v.value !== undefined) return v.value;
                return (typeof v === 'string') ? v : null;
            }).filter(Boolean);
            // Check if zone already has these chips
            var existing = [];
            zone.querySelectorAll('.gb-zone-chip').forEach(function(c) {
                existing.push(c.getAttribute('data-var'));
            });

            _reverseSync = true;  // prevent re-syncing back to dropdown
            values.forEach(function(v) {
                if (v && existing.indexOf(v) === -1) {
                    addVarToZone(zoneId, v);
                }
            });
            _reverseSync = false;
        });

        // Also sync button highlights for chart type, trendline, date group
        syncButtonHighlights(TYPE_BUTTONS, 'gb-chart-type', '#005baa');
        syncButtonHighlights(FIT_BUTTONS, 'gb-trendline', '#7B1FA2');
        syncButtonHighlights(DG_BUTTONS, 'gb-date-group', '#E65100');
    }

    function syncButtonHighlights(buttonMap, dropdownId, activeColor) {
        var dd = document.getElementById(dropdownId);
        if (!dd) return;
        var keys = Object.keys(dd);
        var reactKey = null;
        for (var i = 0; i < keys.length; i++) {
            if (keys[i].indexOf('__reactFiber$') === 0 || keys[i].indexOf('__reactInternalInstance$') === 0) {
                reactKey = keys[i]; break;
            }
        }
        if (!reactKey) return;
        var fiber = dd[reactKey];
        var val = null;
        while (fiber) {
            if (fiber.memoizedProps && fiber.memoizedProps.value !== undefined) {
                val = fiber.memoizedProps.value; break;
            }
            fiber = fiber['return'];
        }
        if (!val) return;
        // Find the button that matches the value
        Object.keys(buttonMap).forEach(function(btnId) {
            var b = document.getElementById(btnId);
            if (!b) return;
            var isActive = buttonMap[btnId] === val;
            b.style.backgroundColor = isActive ? activeColor : '#fff';
            b.style.color = isActive ? '#fff' : '#333';
            b.style.borderColor = isActive ? activeColor : '#e2e8f0';
        });
    }

    // Add a var to zone without syncing back to dropdown (for server-driven sync)
    function addVarToZoneNoSync(zoneId, varName) {
        _reverseSync = true;
        addVarToZone(zoneId, varName);
        _reverseSync = false;
    }

    // Expose globally so Dash callbacks can trigger it
    window.gbSyncDropdownsToZones = syncDropdownsToZones;
    window.gbAddVarToZoneNoSync = addVarToZoneNoSync;
    window.gbSyncButtonHighlights = function() {
        syncButtonHighlights(TYPE_BUTTONS, 'gb-chart-type', '#005baa');
        syncButtonHighlights(FIT_BUTTONS, 'gb-trendline', '#7B1FA2');
        syncButtonHighlights(DG_BUTTONS, 'gb-date-group', '#E65100');
    };
    window.gbSyncButtonHighlightsDirect = function(chartType, trendline, dateGroup) {
        function highlightByValue(buttonMap, val, activeColor) {
            Object.keys(buttonMap).forEach(function(btnId) {
                var b = document.getElementById(btnId);
                if (!b) return;
                var isActive = buttonMap[btnId] === val;
                b.style.backgroundColor = isActive ? activeColor : '#fff';
                b.style.color = isActive ? '#fff' : '#333';
                b.style.borderColor = isActive ? activeColor : '#e2e8f0';
            });
        }
        if (chartType) highlightByValue(TYPE_BUTTONS, chartType, '#005baa');
        if (trendline) highlightByValue(FIT_BUTTONS, trendline, '#7B1FA2');
        if (dateGroup) highlightByValue(DG_BUTTONS, dateGroup, '#E65100');
    };

    function startObserver() {
        var target = document.getElementById('page-graph-builder');
        if (target) {
            observer.observe(target, {childList: true, subtree: true});
        }
    }

    setTimeout(function() { initDragDrop(); startObserver(); }, 1500);
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(function() { initDragDrop(); startObserver(); }, 1500);
    });
})();
