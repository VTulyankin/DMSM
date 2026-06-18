document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("profile-graph-container");
    const tooltip = document.getElementById("profile-graph-tooltip");
    const tooltipValue = document.getElementById("profile-tooltip-value");
    const statusBadge = document.getElementById("player-status-badge");
    const statFirstSeen = document.getElementById("stat-first-seen");
    const statTotalPlaytime = document.getElementById("stat-total-playtime");
    const statAvgSession = document.getElementById("stat-avg-session");
    
    if (!container || !window.API_PLAYER_SESSIONS) return;
    
    let rawSessions = [];
    let firstSeenStr = null;
    let isOnline = false;
    let firstDataTimeMs = new Date().getTime();
    
    let width = container.clientWidth;
    let height = container.clientHeight; // ~450px
    
    const margin = { top: 0, right: 0, bottom: 0, left: 0 };
    const paddingX = 20; // internal padding inside the cards
    
    // Card geometry
    const barCardHeight = 240;
    const gap = 20;
    const ganttCardHeight = 80;
    const MIN_WINDOW_MS = 5 * 60 * 1000; // 5 minutes minimum window
    
    // Y scale for Bar Chart inside its card (leave room for title and axis)
    const yBarScale = d3.scaleLinear().range([barCardHeight - 20, 50]);
    // X scale for both
    const baseXScale = d3.scaleTime().range([paddingX, width - paddingX]);
    let currentXScale = baseXScale;
    
    container.innerHTML = "";
    
    const svg = d3.select(container).append("svg")
        .attr("width", "100%")
        .attr("height", "100%")
        .style("overflow", "visible");
        
    const zoom = d3.zoom()
        .on("zoom", handleZoom);
        
    svg.call(zoom);
    
    // Clip paths for the two cards
    svg.append("defs").append("clipPath")
        .attr("id", "clip-bar")
        .append("rect")
        .attr("x", paddingX).attr("y", 0)
        .attr("width", width - paddingX * 2)
        .attr("height", barCardHeight);
        
    svg.select("defs").append("clipPath")
        .attr("id", "clip-gantt")
        .append("rect")
        .attr("x", paddingX).attr("y", 0)
        .attr("width", width - paddingX * 2)
        .attr("height", ganttCardHeight - 30);
        
    // --------------------------------------------------------
    // Card 1: Bar Chart (Top)
    // --------------------------------------------------------
    const barCardGroup = svg.append("g");
    
    barCardGroup.append("rect")
        .attr("x", 0).attr("y", 0)
        .attr("width", width).attr("height", barCardHeight)
        .attr("fill", "#ffffff")
        .attr("rx", 8)
        .attr("stroke", "#E5E7EB")
        .attr("stroke-width", 1)
        .style("filter", "drop-shadow(0 1px 2px rgba(0,0,0,0.05))");
        
    barCardGroup.append("path")
        .attr("transform", "translate(20, 13)")
        .attr("d", "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z")
        .attr("fill", "none")
        .attr("stroke", "var(--color-blue-500)")
        .attr("stroke-width", "2")
        .attr("stroke-linecap", "round")
        .attr("stroke-linejoin", "round");
        
    barCardGroup.append("text")
        .attr("x", 50).attr("y", 30)
        .attr("font-family", "system-ui, sans-serif")
        .attr("font-size", "18px")
        .attr("font-weight", "bold")
        .attr("fill", "#1F2937")
        .text("Активность игрока");
        
    const barGridGroup = barCardGroup.append("g").attr("clip-path", "url(#clip-bar)");
    const barsGroup = barCardGroup.append("g").attr("clip-path", "url(#clip-bar)");
    
    // --------------------------------------------------------
    // Card 2: Gantt Chart (Bottom)
    // --------------------------------------------------------
    const ganttCardGroup = svg.append("g")
        .attr("transform", `translate(0, ${barCardHeight + gap})`);
        
    ganttCardGroup.append("rect")
        .attr("x", 0).attr("y", 0)
        .attr("width", width).attr("height", ganttCardHeight)
        .attr("fill", "#ffffff")
        .attr("rx", 8)
        .attr("stroke", "#E5E7EB")
        .attr("stroke-width", 1)
        .style("filter", "drop-shadow(0 1px 2px rgba(0,0,0,0.05))");
        
    const ganttGridGroup = ganttCardGroup.append("g").attr("clip-path", "url(#clip-gantt)");
    const ganttBlocksGroup = ganttCardGroup.append("g").attr("clip-path", "url(#clip-gantt)");
    
    const xAxisGroup = ganttCardGroup.append("g")
        .attr("transform", `translate(0, ${ganttCardHeight - 30})`);
        
    let lastTransform = d3.zoomIdentity;
    let isRealtime = true;
    
    // Formatting
    const customTimeFormat = d3.timeFormatLocale({
        dateTime: "%A, %e %B %Y г. %X",
        date: "%d.%m.%Y",
        time: "%H:%M:%S",
        periods: ["AM", "PM"],
        days: ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"],
        shortDays: ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"],
        months: ["Января", "Февраля", "Марта", "Апреля", "Мая", "Июня", "Июля", "Августа", "Сентября", "Октября", "Ноября", "Декабря"],
        shortMonths: ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
    });
    
    const formatMillisecond = customTimeFormat.format(".%L"),
        formatSecond = customTimeFormat.format(":%S"),
        formatMinute = customTimeFormat.format("%H:%M"),
        formatHour = customTimeFormat.format("%H:00"),
        formatDay = customTimeFormat.format("%d %b"),
        formatWeek = customTimeFormat.format("%d %b"),
        formatMonth = customTimeFormat.format("%B"),
        formatYear = customTimeFormat.format("%Y");

    const timeFormat = customTimeFormat.format("%H:%M");
    const dateFormat = customTimeFormat.format("%d %B %Y г.");
    const parseISO = d3.isoParse;
    
    function multiFormat(date) {
        return (d3.timeSecond(date) < date ? formatMillisecond
            : d3.timeMinute(date) < date ? formatSecond
            : d3.timeHour(date) < date ? formatMinute
            : d3.timeDay(date) < date ? formatHour
            : d3.timeMonth(date) < date ? (date.getDay() && date.getDate() !== 1 ? formatDay : formatWeek)
            : d3.timeYear(date) < date ? formatMonth
            : formatYear)(date);
    }
    
    function updateStats(nowMs) {
        if (!firstSeenStr) {
            statFirstSeen.textContent = "Нет данных";
            statTotalPlaytime.textContent = "0 ч. 0 мин.";
            statAvgSession.textContent = "0 мин.";
            return;
        }
        
        statFirstSeen.textContent = dateFormat(parseISO(firstSeenStr));
        
        let totalMs = 0;
        let validSessionsCount = 0;
        let validSessionsTotalMs = 0;
        
        rawSessions.forEach(s => {
            const start = parseISO(s.login).getTime();
            const end = s.logout ? parseISO(s.logout).getTime() : nowMs;
            const durationMs = end - start;
            totalMs += durationMs;
            
            if (durationMs >= 5 * 60 * 1000) {
                validSessionsCount++;
                validSessionsTotalMs += durationMs;
            }
        });
        
        const formatDuration = (ms) => {
            const totalSec = Math.floor(ms / 1000);
            const d = Math.floor(totalSec / 86400);
            const h = Math.floor((totalSec % 86400) / 3600);
            const m = Math.floor((totalSec % 3600) / 60);
            
            if (d > 0) return `${d} д. ${h} ч. ${m} мин.`;
            if (h > 0) return `${h} ч. ${m} мин.`;
            return `${m} мин.`;
        };
        
        statTotalPlaytime.textContent = formatDuration(totalMs);
        
        if (validSessionsCount > 0) {
            statAvgSession.textContent = formatDuration(validSessionsTotalMs / validSessionsCount);
        } else {
            statAvgSession.textContent = "Меньше 5 мин.";
        }
    }
    
    function getDailyData(nowMs) {
        const days = {};
        
        rawSessions.forEach(s => {
            const startMs = parseISO(s.login).getTime();
            const endMs = s.logout ? parseISO(s.logout).getTime() : nowMs;
            
            let current = startMs;
            while (current < endMs) {
                const dateObj = new Date(current);
                const dayStr = `${dateObj.getFullYear()}-${dateObj.getMonth()}-${dateObj.getDate()}`;
                
                const startOfDayObj = new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate());
                const endOfDayMs = startOfDayObj.getTime() + 86400000;
                
                const chunkEnd = Math.min(endMs, endOfDayMs);
                const durationHours = (chunkEnd - current) / 3600000;
                
                if (!days[dayStr]) {
                    days[dayStr] = {
                        startOfDay: startOfDayObj,
                        endOfDay: new Date(endOfDayMs),
                        hours: 0
                    };
                }
                days[dayStr].hours += durationHours;
                
                current = chunkEnd;
            }
        });
        
        return Object.values(days);
    }
    
    function formatDurationString(hours) {
        const totalSec = Math.floor(hours * 3600);
        const h = Math.floor(totalSec / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const s = totalSec % 60;
        if (h > 0) return `${h} ч. ${m} мин.`;
        if (m > 0) return `${m} мин.`;
        return `${s} сек.`;
    }
    
    function drawCharts(nowMs) {
        const ticks = currentXScale.ticks(width / 80);
        
        // --- 1. Bar Chart (Top) ---
        const barLines = barGridGroup.selectAll("line").data(ticks);
        barLines.enter().append("line")
            .attr("y1", 50)
            .attr("y2", barCardHeight - 20)
            .merge(barLines)
            .attr("class", d => d.getHours() === 0 && d.getMinutes() === 0 ? "grid-line-day" : "grid-line")
            .attr("x1", d => currentXScale(d))
            .attr("x2", d => currentXScale(d));
        barLines.exit().remove();
        
        const dailyData = getDailyData(nowMs);
        const currentDomain = currentXScale.domain();
        const visibleDays = dailyData.filter(d => d.endOfDay > currentDomain[0] && d.startOfDay < currentDomain[1]);
        const maxHours = d3.max(visibleDays, d => d.hours) || 1;
        
        yBarScale.domain([0, Math.max(maxHours, 1)]);
        
        const bars = barsGroup.selectAll(".day-bar").data(dailyData);
        bars.enter().append("rect")
            .attr("class", "day-bar cursor-pointer transition-opacity")
            .style("fill", "var(--color-green-500)")
            .on("mouseover", function(event, d) {
                d3.select(this).style("fill", "var(--color-green-600)");
                tooltip.classList.remove("hidden");
                tooltipValue.textContent = formatDurationString(d.hours);
            })
            .on("mousemove", function(event) {
                const bounds = this.getBoundingClientRect();
                const containerBounds = container.getBoundingClientRect();
                const x = event.clientX - containerBounds.left;
                const y = bounds.top - containerBounds.top - 8;
                tooltip.style.left = `${x}px`;
                tooltip.style.top = `${y}px`;
                tooltip.style.transform = "translate(-50%, -100%)";
            })
            .on("mouseout", function() {
                d3.select(this).style("fill", "var(--color-green-500)");
                tooltip.classList.add("hidden");
            })
            .merge(bars)
            .attr("x", d => currentXScale(d.startOfDay) + 1)
            .attr("width", d => Math.max(1, currentXScale(d.endOfDay) - currentXScale(d.startOfDay) - 2))
            .attr("y", d => yBarScale(d.hours))
            .attr("height", d => Math.max(0, (barCardHeight - 20) - yBarScale(d.hours)));
        bars.exit().remove();
        
        // --- 2. Gantt Chart (Bottom) ---
        const ganttLines = ganttGridGroup.selectAll("line").data(ticks);
        ganttLines.enter().append("line")
            .attr("y1", 0)
            .attr("y2", ganttCardHeight - 30)
            .merge(ganttLines)
            .attr("class", d => d.getHours() === 0 && d.getMinutes() === 0 ? "grid-line-day" : "grid-line")
            .attr("x1", d => currentXScale(d))
            .attr("x2", d => currentXScale(d));
        ganttLines.exit().remove();
        
        const ganttData = rawSessions.map(s => {
            return {
                start: parseISO(s.login).getTime(),
                end: s.logout ? parseISO(s.logout).getTime() : nowMs,
                isLive: !s.logout
            };
        });
        
        const blocks = ganttBlocksGroup.selectAll(".session-block").data(ganttData);
        blocks.enter().append("rect")
            .attr("class", "session-block cursor-pointer transition-colors")
            .attr("y", (ganttCardHeight - 30) / 2 - 15) // center vertically
            .attr("height", 30)
            .attr("rx", 4)
            .style("fill", "var(--color-green-500)") // Green
            .on("mouseover", function(event, d) {
                d3.select(this).style("fill", "var(--color-green-600)"); // Darker green on hover
                tooltip.classList.remove("hidden");
                const durationHours = (d.end - d.start) / 3600000;
                tooltipValue.textContent = formatDurationString(durationHours);
            })
            .on("mousemove", function(event) {
                const bounds = this.getBoundingClientRect();
                const containerBounds = container.getBoundingClientRect();
                const x = event.clientX - containerBounds.left;
                const y = bounds.top - containerBounds.top - 8;
                tooltip.style.left = `${x}px`;
                tooltip.style.top = `${y}px`;
                tooltip.style.transform = "translate(-50%, -100%)";
            })
            .on("mouseout", function(event, d) {
                d3.select(this).style("fill", "var(--color-green-500)");
                tooltip.classList.add("hidden");
            })
            .merge(blocks)
            .attr("x", d => Math.max(paddingX, currentXScale(new Date(d.start))))
            .attr("width", d => {
                const x1 = Math.max(paddingX, currentXScale(new Date(d.start)));
                const x2 = Math.min(width - paddingX, currentXScale(new Date(d.end)));
                return Math.max(0, x2 - x1);
            });
        blocks.exit().remove();
        
        const xAxis = d3.axisBottom(currentXScale)
            .tickFormat(multiFormat)
            .tickSizeOuter(0)
            .ticks(width / 80);
            
        xAxisGroup.call(xAxis);
        xAxisGroup.select(".domain").remove();
        xAxisGroup.selectAll(".tick line").remove();
    }
    
    function handleZoom(event) {
        if (!firstSeenStr) return;
        
        let t = event.transform;
        const nowMs = new Date().getTime();
        
        // Right constraint
        const tempScale = t.rescaleX(baseXScale);
        let domain = tempScale.domain();
        
        if (domain[1].getTime() > nowMs) {
            t.x = (width - paddingX) - t.k * baseXScale(new Date(nowMs));
            isRealtime = true;
        } else {
            isRealtime = (nowMs - domain[1].getTime() < 5000);
        }
        
        // Left constraint
        const tempScale2 = t.rescaleX(baseXScale);
        domain = tempScale2.domain();
        
        if (domain[0].getTime() < firstDataTimeMs) {
            t.x = paddingX - t.k * baseXScale(new Date(firstDataTimeMs));
            
            // Re-check right constraint if forced left
            const tempScale3 = t.rescaleX(baseXScale);
            if (tempScale3.domain()[1].getTime() > nowMs) {
                // Reset to full view
                t.k = (width - paddingX * 2) / (baseXScale(new Date(nowMs)) - baseXScale(new Date(firstDataTimeMs)));
                t.x = paddingX - t.k * baseXScale(new Date(firstDataTimeMs));
                isRealtime = true;
            }
        }
        
        if (event.transform.x !== t.x || event.transform.k !== t.k) {
            svg.node().__zoom = t;
        }
        
        lastTransform = t;
        currentXScale = t.rescaleX(baseXScale);
        
        drawCharts(nowMs);
    }
    
    function realtimeTick() {
        const nowMs = new Date().getTime();
        
        if (isRealtime && firstSeenStr) {
            const k = lastTransform.k;
            const tx = (width - paddingX) - k * baseXScale(new Date(nowMs));
            const t = d3.zoomIdentity.translate(tx, 0).scale(k);
            
            svg.node().__zoom = t;
            lastTransform = t;
            currentXScale = t.rescaleX(baseXScale);
        }
        
        updateStats(nowMs);
        drawCharts(nowMs);
    }
    
    async function fetchData() {
        try {
            const resp = await fetch(window.API_PLAYER_SESSIONS);
            const data = await resp.json();
            
            if (data.error) return;
            
            rawSessions = data.sessions;
            firstSeenStr = data.first_seen;
            isOnline = data.status === 'online';
            
            if (isOnline) {
                statusBadge.textContent = "ONLINE";
                statusBadge.className = "ml-3 px-2 py-1 text-[10px] leading-none flex items-center font-bold uppercase rounded-full bg-green-100 text-green-600 border border-green-200";
            } else {
                statusBadge.textContent = "OFFLINE";
                statusBadge.className = "ml-3 px-2 py-1 text-[10px] leading-none flex items-center font-bold uppercase rounded-full bg-gray-100 text-gray-500 border border-gray-200";
            }
            
            if (firstSeenStr) {
                firstDataTimeMs = parseISO(firstSeenStr).getTime() - 86400000;
                const nowMs = new Date().getTime();
                baseXScale.domain([new Date(firstDataTimeMs), new Date(nowMs)]);
                
                // Set initial zoom to last 7 days
                const initialStart = Math.max(firstDataTimeMs, nowMs - 7 * 86400000);
                const k = (width - paddingX * 2) / (baseXScale(new Date(nowMs)) - baseXScale(new Date(initialStart)));
                const tx = (width - paddingX) - k * baseXScale(new Date(nowMs));
                
                const t = d3.zoomIdentity.translate(tx, 0).scale(k);
                
                // Set zoom limits dynamically
                const totalMs = nowMs - firstDataTimeMs;
                const maxK = totalMs / MIN_WINDOW_MS;
                zoom.scaleExtent([1, Math.max(1, maxK)]);
                
                svg.call(zoom.transform, t);
            }
            
            updateStats(new Date().getTime());
        } catch (e) {
            console.error(e);
        }
    }
    
    window.addEventListener("resize", () => {
        width = container.clientWidth;
        height = container.clientHeight;
        
        baseXScale.range([paddingX, width - paddingX]);
        currentXScale.range([paddingX, width - paddingX]);
        
        svg.select("#clip-bar rect").attr("width", width - paddingX * 2);
        svg.select("#clip-gantt rect").attr("width", width - paddingX * 2);
        
        barCardGroup.select("rect").attr("width", width);
        ganttCardGroup.select("rect").attr("width", width);
        
        drawCharts(new Date().getTime());
    });
    
    fetchData();
    setInterval(realtimeTick, 1000);
});
