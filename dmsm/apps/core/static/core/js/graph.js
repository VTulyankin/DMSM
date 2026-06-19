document.addEventListener("DOMContentLoaded", () => {
    // Setup Russian locale for D3 time formatting
    d3.timeFormatDefaultLocale({
        dateTime: "%A, %e %B %Y г. %X",
        date: "%d.%m.%Y",
        time: "%H:%M:%S",
        periods: ["AM", "PM"],
        days: ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"],
        shortDays: ["вс", "пн", "вт", "ср", "чт", "пт", "сб"],
        months: ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"],
        shortMonths: ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
    });

    const container = document.getElementById("graph-container");
    if (!container) return;

    // --- Configurations ---
    let height = container.clientHeight;
    let width = container.clientWidth;
    
    const margin = { top: 40, right: 30, bottom: 40, left: 0 };
    
    let innerWidth = width - margin.left - margin.right;
    let innerHeight = height - margin.top - margin.bottom;

    const MIN_WINDOW_MS = 5 * 60 * 1000; 
    const MAX_WINDOW_MS = 365 * 24 * 60 * 60 * 1000;

    // --- D3 Setup ---
    const svg = d3.select("#graph-container")
        .append("svg")
        .attr("width", "100%")
        .attr("height", "100%")
        .style("overflow", "hidden");

    // Defs for gradient
    const defs = svg.append("defs");
    
    // Gradient uses userSpaceOnUse so offset="0.5" corresponds to 50% of the SVG width
    const lineGradient = defs.append("linearGradient")
        .attr("id", "line-gradient")
        .attr("gradientUnits", "userSpaceOnUse")
        .attr("x1", 0).attr("y1", 0)
        .attr("x2", innerWidth + 20).attr("y2", 0);

    // Clip path allows dot to show outside innerWidth by extending width slightly
    svg.append("clipPath")
        .attr("id", "graph-clip")
        .append("rect")
        .attr("x", 0)
        .attr("y", -margin.top)
        .attr("width", innerWidth + 20)
        .attr("height", height + margin.bottom);

    const g = svg.append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);
        
    const clipG = g.append("g").attr("clip-path", "url(#graph-clip)");

    const baseMinTime = new Date('2020-01-01').getTime();
    const baseMaxTime = new Date('2030-01-01').getTime();
    let baseXScale = d3.scaleTime()
        .domain([new Date(baseMinTime), new Date(baseMaxTime)])
        .range([0, innerWidth]);
        
    let currentXScale = baseXScale.copy();
    let yScale = d3.scaleLinear().range([innerHeight, 0]);

    const gridG = clipG.append("g").attr("class", "grid");
    // Only one line path now, using the gradient!
    const linePath = clipG.append("path").attr("class", "graph-line");
    
    // Bottom X Axis
    const xAxisG = g.append("g")
        .attr("class", "x-axis")
        .attr("transform", `translate(0,${innerHeight})`)
        .style("color", "#9ca3af")
        .style("font-size", "11px");

    const endDot = clipG.append("circle")
        .attr("class", "end-dot")
        .attr("r", 5)
        .style("fill", "var(--color-green-500)")
        .style("filter", "drop-shadow(0 0 6px rgba(34,197,94,0.6))")
        .style("display", "none");
        
    const clickPin = clipG.append("circle")
        .attr("class", "click-pin")
        .attr("r", 5)
        .style("fill", "white")
        .style("stroke", "var(--color-blue-500)")
        .style("stroke-width", "3px")
        .style("filter", "drop-shadow(0 2px 4px rgba(0,0,0,0.3))")
        .style("display", "none");

    // --- State ---
    let processedData = []; 
    let isRealtime = true; 
    let firstDataTimeMs = new Date().getTime();
    let activeClickTimeMs = null;

    const tooltip = document.getElementById("graph-tooltip");
    const tooltipValue = document.getElementById("tooltip-value");
    const tooltipDot = document.getElementById("tooltip-dot");
    const currentOnlineEl = document.getElementById("current-online-count");
    const zoomIndicatorEl = document.getElementById("zoom-indicator");

    // D3 Zoom Behavior
    const zoom = d3.zoom()
        .scaleExtent([
            (baseMaxTime - baseMinTime) / MAX_WINDOW_MS, 
            (baseMaxTime - baseMinTime) / MIN_WINDOW_MS
        ])
        .on("zoom", handleZoom)
        .filter(e => !e.button && e.type !== "dblclick");

    svg.call(zoom);

    let lastTransform = d3.zoomIdentity;
    let initialZoomDone = false;

    function handleZoom(event) {
        if (processedData.length === 0) return;
        
        let t = event.transform;
        
        const tempScale = t.rescaleX(baseXScale);
        let domain = tempScale.domain();
        
        const nowMs = new Date().getTime();
        
        // Right constraint
        if (domain[1].getTime() > nowMs) {
            t.x = innerWidth - t.k * baseXScale(new Date(nowMs));
            isRealtime = true;
        } else {
            isRealtime = (nowMs - domain[1].getTime() < 5000);
        }
        
        // Left constraint
        const tempScale2 = t.rescaleX(baseXScale);
        domain = tempScale2.domain();
        
        if (domain[0].getTime() < firstDataTimeMs) {
            t.x = -t.k * baseXScale(new Date(firstDataTimeMs));
            
            const tempScale3 = t.rescaleX(baseXScale);
            if (tempScale3.domain()[1].getTime() > nowMs) {
                const requiredWindowMs = nowMs - firstDataTimeMs;
                if (requiredWindowMs > MIN_WINDOW_MS) {
                    t.k = (baseMaxTime - baseMinTime) / requiredWindowMs;
                    t.x = -t.k * baseXScale(new Date(firstDataTimeMs));
                }
                isRealtime = true;
            }
        }
        
        if (event.transform.x !== t.x || event.transform.k !== t.k) {
            svg.node().__zoom = t;
        }
        
        lastTransform = t;
        currentXScale = t.rescaleX(baseXScale);
        
        updateZoomIndicator();
        window.hovering = false; 
        tooltip.classList.add("hidden");
        
        render();
    }

    function updateZoomIndicator() {
        if (!zoomIndicatorEl) return;
        const windowMs = currentXScale.domain()[1].getTime() - currentXScale.domain()[0].getTime();
        
        let text = "";
        if (windowMs < 60 * 60 * 1000) {
            text = "Минуты";
        } else if (windowMs < 24 * 60 * 60 * 1000) {
            text = "Часы";
        } else if (windowMs < 7 * 24 * 60 * 60 * 1000) {
            text = "Дни";
        } else if (windowMs < 30 * 24 * 60 * 60 * 1000) {
            text = "Недели";
        } else {
            text = "Месяцы";
        }
        zoomIndicatorEl.textContent = text;
    }

    // --- Corner Rounding Algorithm ---
    function generateRoundedPath(data) {
        if (!data || data.length === 0) return "";
        
        const geomData = data.filter(d => !d.isArtificial);
        if (geomData.length === 0) return "";
        
        const essentialData = [];
        for (let i = 0; i < geomData.length; i++) {
            if (i === 0 || i === geomData.length - 1) {
                essentialData.push(geomData[i]);
            } else if (geomData[i].value !== geomData[i-1].value) {
                essentialData.push(geomData[i]);
            }
        }
        
        const rawPoints = [];
        for (let i = 0; i < essentialData.length; i++) {
            const pt = essentialData[i];
            const x = currentXScale(pt.time);
            const y = yScale(pt.value);
            
            if (i === 0) {
                rawPoints.push({x, y});
            } else {
                const prev = essentialData[i-1];
                const prevY = yScale(prev.value);
                // Step Corner
                rawPoints.push({x: x, y: prevY}); 
                // Next Point
                rawPoints.push({x: x, y: y});     
            }
        }
        
        if (rawPoints.length < 2) return "";
        
        let path = `M ${rawPoints[0].x},${rawPoints[0].y} `;
        const r = 4;
        
        for (let i = 1; i < rawPoints.length - 1; i++) {
            const p0 = rawPoints[i-1];
            const p1 = rawPoints[i];
            const p2 = rawPoints[i+1];
            
            const dx1 = p1.x - p0.x;
            const dy1 = p1.y - p0.y;
            const len1 = Math.sqrt(dx1*dx1 + dy1*dy1);
            
            const dx2 = p2.x - p1.x;
            const dy2 = p2.y - p1.y;
            const len2 = Math.sqrt(dx2*dx2 + dy2*dy2);
            
            if (len1 < 0.1 || len2 < 0.1) {
                path += `L ${p1.x},${p1.y} `;
                continue;
            }
            
            const actualR = Math.min(r, len1/2, len2/2);
            
            if (actualR < 1) {
                path += `L ${p1.x},${p1.y} `;
                continue;
            }
            
            const startX = p1.x - (dx1/len1) * actualR;
            const startY = p1.y - (dy1/len1) * actualR;
            
            const endX = p1.x + (dx2/len2) * actualR;
            const endY = p1.y + (dy2/len2) * actualR;
            
            path += `L ${startX},${startY} `;
            
            const cross = (dx1/len1) * (dy2/len2) - (dy1/len1) * (dx2/len2);
            const sweep = cross > 0 ? 1 : 0;
            
            path += `A ${actualR} ${actualR} 0 0 ${sweep} ${endX} ${endY} `;
        }
        
        const last = rawPoints[rawPoints.length-1];
        path += `L ${last.x},${last.y}`;
        return path;
    }

    // --- Exact Hover & Click Position ---
    function getExactYAtX(xPx) {
        if (processedData.length === 0) return { y: 0, val: 0, status: 'online' };
        
        const rawPoints = [];
        for (let i = 0; i < processedData.length; i++) {
            const pt = processedData[i];
            const x = currentXScale(pt.time);
            const y = yScale(pt.value);
            if (i === 0) {
                rawPoints.push({x, y, val: pt.value, status: pt.status});
            } else {
                const prev = processedData[i-1];
                const prevY = yScale(prev.value);
                rawPoints.push({x: x, y: prevY, val: prev.value, status: prev.status});
                rawPoints.push({x: x, y: y, val: pt.value, status: pt.status});
            }
        }
        
        const r = 4;
        
        for (let i = 1; i < rawPoints.length - 1; i++) {
            const p0 = rawPoints[i-1];
            const p1 = rawPoints[i];
            const p2 = rawPoints[i+1];
            
            const dx1 = p1.x - p0.x;
            const dy1 = p1.y - p0.y;
            const len1 = Math.sqrt(dx1*dx1 + dy1*dy1);
            
            const dx2 = p2.x - p1.x;
            const dy2 = p2.y - p1.y;
            const len2 = Math.sqrt(dx2*dx2 + dy2*dy2);
            
            if (len1 < 0.1 || len2 < 0.1) continue;
            
            const actualR = Math.min(r, len1/2, len2/2);
            if (actualR < 1) continue;
            
            const startX = p1.x - (dx1/len1) * actualR;
            const endX = p1.x + (dx2/len2) * actualR;
            
            const minX = Math.min(startX, endX);
            const maxX = Math.max(startX, endX);
            
            if (xPx >= minX && xPx <= maxX) {
                const isHorizontalFirst = Math.abs(dy1) < 0.1;
                const cx = isHorizontalFirst ? p1.x - (dx1/len1) * actualR : p1.x + (dx2/len2) * actualR;
                const cy = isHorizontalFirst ? p1.y + (dy2/len2) * actualR : p1.y - (dy1/len1) * actualR;
                
                const sq = Math.max(0, actualR * actualR - (xPx - cx)*(xPx - cx));
                const dy = Math.sqrt(sq);
                
                const targetY = p1.y; 
                const sign = targetY > cy ? 1 : -1;
                const exactY = cy + sign * dy;
                
                const segVal = isHorizontalFirst ? p0.val : p1.val;
                const segStatus = isHorizontalFirst ? p0.status : p1.status;
                
                return {y: exactY, val: segVal, status: segStatus};
            }
        }
        
        for (let i = 0; i < rawPoints.length - 1; i++) {
            const p1 = rawPoints[i];
            const p2 = rawPoints[i+1];
            if (Math.abs(p1.x - p2.x) > 0.1) {
                const minX = Math.min(p1.x, p2.x);
                const maxX = Math.max(p1.x, p2.x);
                if (xPx >= minX && xPx <= maxX) {
                    return {y: p1.y, val: p1.val, status: p1.status};
                }
            }
        }
        
        const last = rawPoints[rawPoints.length-1];
        return {y: last.y, val: last.val, status: last.status};
    }

    // Helper: Map status string to color
    function getStatusColor(status) {
        if (status === 'offline') return 'var(--color-gray-400)';
        if (status === 'downtime') return 'var(--color-red-500)';
        if (status === 'degraded') return 'var(--color-yellow-500)';
        return 'var(--color-green-500)';
    }

    // --- Data Processing ---
    async function fetchData() {
        try {
            const response = await fetch(window.API_ONLINE_EVENTS);
            const data = await response.json();
            
            processedData = [];
            
            let nowMs = new Date().getTime();
            let timeSet = new Set();
            let artificialTimes = new Set();
            data.events.forEach(e => timeSet.add(new Date(e.time).getTime()));
            data.monitors.forEach(m => {
                const s = new Date(m.start).getTime();
                const e = new Date(m.end).getTime();
                timeSet.add(s);
                timeSet.add(e);
                const art = e + 60001;
                timeSet.add(art); // Sharp transition to offline after 1 min
                artificialTimes.add(art);
            });
            let times = Array.from(timeSet)
                .sort((a, b) => a - b)
                .filter(t => t <= nowMs);
            
            let lastVal = 0;
            let lastServerStatus = 'online';
            let eIdx = 0;
            
            for (const tMs of times) {
                let isRealEvent = false;
                while (eIdx < data.events.length && new Date(data.events[eIdx].time).getTime() <= tMs) {
                    const ev = data.events[eIdx];
                    if (new Date(ev.time).getTime() === tMs) {
                        isRealEvent = true;
                    }
                    if (ev.type === 'downtime') {
                        lastVal = 0;
                        lastServerStatus = 'downtime';
                    } else if (ev.type === 'uptime') {
                        lastVal = ev.player_count || 0;
                        lastServerStatus = 'online';
                    }
                    eIdx++;
                }
                
                let monitorMode = 'offline';
                for (const m of data.monitors) {
                    const mStart = new Date(m.start).getTime();
                    const mEnd = new Date(m.end).getTime();
                    if (tMs >= mStart && tMs <= mEnd + 60000) {
                        monitorMode = m.mode;
                        break;
                    }
                }
                
                let finalStatus = 'online';
                if (monitorMode === 'offline') {
                    finalStatus = 'offline';
                } else if (lastServerStatus === 'downtime') {
                    finalStatus = 'downtime';
                } else if (monitorMode !== 'full') {
                    finalStatus = 'degraded';
                }
                
                processedData.push({
                    time: new Date(tMs),
                    value: lastVal,
                    status: finalStatus,
                    isArtificial: artificialTimes.has(tMs) && !isRealEvent
                });
            }
            
            if (processedData.length > 0) {
                firstDataTimeMs = processedData[0].time.getTime();
            }
            
            let currentMonitorMode = 'offline';
            for (const m of data.monitors) {
                const mStart = new Date(m.start).getTime();
                const mEnd = new Date(m.end).getTime();
                if (nowMs >= mStart && nowMs <= mEnd + 60000) {
                    currentMonitorMode = m.mode;
                    break;
                }
            }
            
            let currentStatus = 'online';
            if (currentMonitorMode === 'offline') {
                currentStatus = 'offline';
            } else if (lastServerStatus === 'downtime') {
                currentStatus = 'downtime';
            } else if (currentMonitorMode !== 'full') {
                currentStatus = 'degraded';
            }
            
            let currentVal = processedData.length > 0 ? processedData[processedData.length - 1].value : 0;
            
            processedData.push({
                time: new Date(nowMs),
                value: currentVal,
                status: currentStatus
            });
            
            if (!initialZoomDone && processedData.length > 0) {
                initialZoomDone = true;
                const nowMs = new Date().getTime();
                const totalAvailMs = nowMs - firstDataTimeMs;
                const startWindowMs = Math.min(totalAvailMs, 2 * 60 * 60 * 1000); 
                
                const k = (baseMaxTime - baseMinTime) / startWindowMs;
                const tx = innerWidth - k * baseXScale(new Date(nowMs));
                
                const initT = d3.zoomIdentity.translate(tx, 0).scale(k);
                svg.call(zoom.transform, initT);
                lastTransform = initT;
                currentXScale = initT.rescaleX(baseXScale);
                updateZoomIndicator();
            }
            
            updateUI(currentVal, currentStatus);
            render();
            
        } catch (error) {
            console.error("Error fetching graph data:", error);
        }
    }

    function updateUI(online, status) {
        if (status === 'offline') {
            currentOnlineEl.textContent = "Нет связи";
            currentOnlineEl.className = "text-2xl sm:text-3xl font-black text-gray-400 drop-shadow-sm transition-colors cursor-pointer hover:text-gray-300";
        } else if (status === 'downtime') {
            currentOnlineEl.textContent = "Откл";
            currentOnlineEl.className = "text-4xl font-black text-red-500 drop-shadow-sm transition-colors cursor-pointer hover:text-red-400";
        } else if (status === 'degraded') {
            currentOnlineEl.textContent = online;
            currentOnlineEl.className = "text-4xl font-black text-yellow-500 drop-shadow-sm transition-colors cursor-pointer hover:text-yellow-400";
        } else {
            currentOnlineEl.textContent = online;
            currentOnlineEl.className = "text-4xl font-black text-green-500 drop-shadow-sm transition-colors cursor-pointer hover:text-green-400";
        }
    }

    // --- Render Loop ---
    function render() {
        if (processedData.length === 0) return;

        const now = new Date();
        processedData[processedData.length - 1].time = now;

        const domain = currentXScale.domain();
        
        // Find visible data for Y scaling
        // To properly find true max within view, we evaluate at domain start
        let valAtStart = 0;
        for (let i = 0; i < processedData.length; i++) {
            if (processedData[i].time > domain[0]) break;
            valAtStart = processedData[i].value;
        }
        
        const visibleData = processedData.filter(d => d.time >= domain[0] && d.time <= domain[1]);
        let maxVal = Math.max(valAtStart, d3.max(visibleData, d => d.value) || 0);
        maxVal = Math.max(maxVal, 1); 
        
        yScale.domain([0, maxVal * 1.2]); // Dynamic scale relative to visible values + 20% padding

        // 1. Draw geometric shape
        linePath.attr("d", generateRoundedPath(processedData));

        // 2. Build Linear Gradient for multiple colors
        let stops = [];
        let currentStatus = processedData[0].status;
        let c = getStatusColor(currentStatus);
        
        stops.push({ offset: 0, color: c });
        
        for (let i = 1; i < processedData.length; i++) {
            const pt = processedData[i];
            if (pt.status !== currentStatus) {
                const px = currentXScale(pt.time);
                // Clamp ratio between 0 and 1 relative to innerWidth + 20
                const ratio = Math.max(0, Math.min(1, px / (innerWidth + 20)));
                
                stops.push({ offset: ratio, color: c });
                
                currentStatus = pt.status;
                c = getStatusColor(currentStatus);
                
                stops.push({ offset: ratio, color: c });
            }
        }
        stops.push({ offset: 1, color: c });
        
        // Apply gradient stops
        const stopSelection = lineGradient.selectAll("stop").data(stops);
        stopSelection.enter().append("stop")
            .merge(stopSelection)
            .attr("offset", d => d.offset)
            .attr("stop-color", d => d.color);
        stopSelection.exit().remove();

        // X Axis Rendering
        const xAxis = d3.axisBottom(currentXScale)
            .ticks(Math.max(2, Math.floor(innerWidth / 100)))
            .tickFormat(d => {
                const windowMs = domain[1].getTime() - domain[0].getTime();
                if (windowMs < 24 * 60 * 60 * 1000) {
                    return d3.timeFormat("%H:%M")(d);
                } else if (windowMs < 7 * 24 * 60 * 60 * 1000) {
                    return d3.timeFormat("%a %H:%M")(d);
                } else {
                    return d3.timeFormat("%d %b")(d);
                }
            })
            .tickSizeOuter(0);
            
        xAxisG.call(xAxis);
        
        // Emphasize day ticks if necessary
        xAxisG.selectAll(".tick").attr("class", d => {
            return (d.getHours() === 0 && d.getMinutes() === 0) ? "tick day-tick" : "tick";
        });
        
        // Vertical grid lines
        const xTicks = currentXScale.ticks(Math.max(2, Math.floor(innerWidth / 100)));
        const vLines = gridG.selectAll(".grid-line-v").data(xTicks);
        vLines.enter()
            .append("line")
            .attr("class", d => (d.getHours() === 0 && d.getMinutes() === 0) ? "grid-line grid-line-v grid-line-day" : "grid-line grid-line-v")
            .merge(vLines)
            .attr("class", d => (d.getHours() === 0 && d.getMinutes() === 0) ? "grid-line grid-line-v grid-line-day" : "grid-line grid-line-v")
            .attr("x1", d => currentXScale(d))
            .attr("x2", d => currentXScale(d))
            .attr("y1", 0)
            .attr("y2", innerHeight);
        vLines.exit().remove();
        
        // Current endpoint dot logic
        if (isRealtime) {
            const lastData = processedData[processedData.length - 1];
            const px = currentXScale(now);
            const py = yScale(lastData.value);
            
            endDot.style("display", "block")
                  .attr("cx", px)
                  .attr("cy", py)
                  .style("fill", getStatusColor(lastData.status))
                  .style("filter", `drop-shadow(0 0 6px ${getStatusColor(lastData.status)})`);
        } else {
            endDot.style("display", "none");
        }
        
        // Render Active Click Pin
        if (activeClickTimeMs) {
            const px = currentXScale(new Date(activeClickTimeMs));
            // Only draw if within bounds
            if (px >= 0 && px <= innerWidth) {
                const info = getExactYAtX(px);
                clickPin.style("display", "block")
                    .attr("cx", px)
                    .attr("cy", info.y);
            } else {
                clickPin.style("display", "none");
            }
        } else {
            clickPin.style("display", "none");
        }
        
        if (window.hovering) {
            updateHoverPos();
        }
    }

    function realtimeTick() {
        if (processedData.length === 0) return;
        
        if (isRealtime && initialZoomDone) {
            const now = new Date();
            const k = lastTransform.k;
            const tx = innerWidth - k * baseXScale(now);
            const t = d3.zoomIdentity.translate(tx, 0).scale(k);
            
            svg.node().__zoom = t;
            lastTransform = t;
            currentXScale = t.rescaleX(baseXScale);
        }
        
        render();
    }

    // --- Interaction ---
    const hoverRect = svg.append("rect")
        .attr("width", innerWidth)
        .attr("height", innerHeight)
        .attr("transform", `translate(${margin.left},${margin.top})`)
        .style("fill", "none")
        .style("pointer-events", "all")
        .on("mousemove", handleHover)
        .on("mouseleave", () => {
            window.hovering = false;
            tooltip.classList.add("hidden");
        })
        .on("click", handleClick);

    let lastMouseX = 0;

    function handleHover(e) {
        window.hovering = true;
        const rect = hoverRect.node().getBoundingClientRect();
        lastMouseX = e.clientX - rect.left;
        updateHoverPos();
    }
    
    function updateHoverPos() {
        if (!window.hovering) return;
        
        const info = getExactYAtX(lastMouseX);
        
        tooltipValue.textContent = info.val;
        
        const px = lastMouseX + margin.left;
        const py = info.y + margin.top;
        
        tooltip.style.left = `${px}px`;
        tooltip.style.top = `${py}px`; 
        
        tooltip.classList.remove("hidden");
        tooltipValue.parentElement.classList.remove("hidden");
        tooltip.style.transform = `translate(-50%, -100%)`; 
        
        let colorClass = 'border-green-500';
        if (info.status === 'offline') {
            tooltipValue.textContent = 'Нет связи';
            colorClass = 'border-gray-400';
        } else if (info.status === 'downtime') {
            tooltipValue.textContent = 'Откл';
            colorClass = 'border-red-500';
        } else if (info.status === 'degraded') {
            tooltipValue.textContent = info.val;
            colorClass = 'border-yellow-500';
        } else {
            tooltipValue.textContent = info.val;
        }
        
        tooltipDot.className = `w-3 h-3 bg-white rounded-full shadow-[0_0_8px_rgba(255,255,255,0.8)] transition-colors border-2 absolute -bottom-1.5 left-1/2 -ml-1.5 ${colorClass}`;
    }

    async function loadPlayersList(timestampMs) {
        const listContainer = document.getElementById("players-list-container");
        const titleEl = document.getElementById("players-list-title");
        
        listContainer.innerHTML = '<p class="text-gray-500 animate-pulse">Загрузка списка игроков...</p>';
        
        if (titleEl) {
            const svgIcon = `<svg class="w-5 h-5 mr-2 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>`;
            if (timestampMs) {
                const dateStr = d3.timeFormat("%d %b %Y г., %H:%M")(new Date(timestampMs));
                titleEl.innerHTML = svgIcon + `Игроки онлайн <span class="text-gray-500 text-lg ml-2 font-medium">(${dateStr})</span>`;
            } else {
                titleEl.innerHTML = svgIcon + "Игроки онлайн";
            }
        }
        
        try {
            const query = timestampMs ? `timestamp=${timestampMs}` : 'timestamp=now';
            const resp = await fetch(`${window.API_PLAYERS_AT_TIME}?${query}`);
            const data = await resp.json();
            
            if (data.error) {
                listContainer.innerHTML = `<p class="text-red-500">Ошибка: ${data.error}</p>`;
                return;
            }
            
            if (data.players.length === 0) {
                if (timestampMs) {
                    listContainer.innerHTML = `<p class="text-gray-500 italic">В этот момент на сервере никого не было.</p>`;
                } else {
                    listContainer.innerHTML = `<p class="text-gray-500 italic">Сейчас на сервере никого нет.</p>`;
                }
                return;
            }
            
            let html = `<div class="grid grid-cols-2 md:grid-cols-4 gap-4">`;
            data.players.forEach(p => {
                const uuid = p.uuid ? p.uuid.replace(/-/g, '') : p.username;
                html += `
                    <a href="/users/${p.username}/" class="group flex items-center space-x-3 bg-gray-50 p-2 rounded border border-gray-100 hover:border-green-400 hover:shadow-sm transition-all cursor-pointer">
                        <img src="https://api.mineatar.io/head/${uuid}?scale=16" alt="${p.username}" class="w-8 h-auto object-contain drop-shadow-sm" onerror="this.src='https://api.mineatar.io/head/MHF_Steve?scale=16'">
                        <span class="font-semibold text-gray-700 group-hover:text-green-600 transition-colors">${p.username}</span>
                    </a>
                `;
            });
            html += `</div>`;
            listContainer.innerHTML = html;
            
        } catch (error) {
            listContainer.innerHTML = `<p class="text-red-500">Ошибка при получении данных.</p>`;
        }
    }

    async function handleClick(e) {
        const rect = hoverRect.node().getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const hoveredTime = currentXScale.invert(mx);
        const timestampMs = hoveredTime.getTime();
        
        // Lock the click pin at this time
        activeClickTimeMs = timestampMs;
        render(); // Immediately render the click pin to avoid 1-second delay
        loadPlayersList(timestampMs);
    }
    
    // Add reset to "now" on currentOnlineEl click
    currentOnlineEl.addEventListener("click", () => {
        if (activeClickTimeMs === null && isRealtime) return; // Already there
        
        activeClickTimeMs = null;
        isRealtime = false; // Disable realtime lock during animation
        
        const nowMs = new Date().getTime();
        const k = lastTransform.k;
        const tx = innerWidth - k * baseXScale(new Date(nowMs));
        
        const t = d3.zoomIdentity.translate(tx, 0).scale(k);
        svg.transition()
            .duration(750)
            .ease(d3.easeCubicOut)
            .call(zoom.transform, t)
            .on("end", () => {
                isRealtime = true; // Re-enable lock after animation finishes
            });
        
        loadPlayersList(null);
    });

    window.addEventListener("resize", () => {
        width = container.clientWidth;
        height = container.clientHeight;
        innerWidth = width - margin.left - margin.right;
        innerHeight = height - margin.top - margin.bottom;
        
        baseXScale.range([0, innerWidth]);
        currentXScale.range([0, innerWidth]);
        yScale.range([innerHeight, 0]);
        
        hoverRect.attr("width", innerWidth).attr("height", innerHeight);
        svg.select("#graph-clip rect")
            .attr("width", innerWidth + 20)
            .attr("height", height + margin.bottom);
            
        xAxisG.attr("transform", `translate(0,${innerHeight})`);
        lineGradient.attr("x2", innerWidth + 20);
        
        render();
    });
    
    fetchData();
    loadPlayersList(null); // Load current players on initial load
    setInterval(realtimeTick, 1000);
    setInterval(() => {
        fetchData();
        // Auto-refresh players if we are in live mode
        if (activeClickTimeMs === null) {
            loadPlayersList(null);
        }
    }, 10000);
});
