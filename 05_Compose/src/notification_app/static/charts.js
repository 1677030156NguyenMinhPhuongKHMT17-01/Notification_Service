/**
 * Pure offline SVG chart & pipeline visualizers for Smart Campus Notification Center.
 * Exposes window.DemoCharts without any external library dependencies.
 */
(function (global) {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function toCount(value) {
    var n = Number(value);
    if (!Number.isFinite(n) || n < 0) return 0;
    return Math.round(n);
  }

  var STATUS_SPECS = [
    { key: "delivered", label: "Delivered", color: "#22C55E" },
    { key: "retrying", label: "Retrying", color: "#F59E0B" },
    { key: "failed", label: "Failed / DLQ", color: "#EF4444" },
    { key: "duplicate_ignored", label: "Suppressed", color: "#38BDF8" },
    { key: "queued", label: "Queued", color: "#94A3B8" }
  ];

  var CHANNEL_SPECS = [
    { key: "telegram", label: "Telegram", color: "#38BDF8" },
    { key: "email", label: "Email", color: "#22C55E" },
    { key: "discord", label: "Discord", color: "#818CF8" },
    { key: "sms", label: "SMS", color: "#F59E0B" }
  ];

  var PIPELINE_STAGES = [
    { key: "core", title: "Core Business", subtitle: "Nhóm 5 Source" },
    { key: "mqtt", title: "Transport", subtitle: "MQTT / REST" },
    { key: "validator", title: "Validator", subtitle: "Pydantic v2 + Q09" },
    { key: "store", title: "PostgreSQL", subtitle: "Idempotent Log" },
    { key: "delivery", title: "Delivery", subtitle: "Channel Adapters" }
  ];

  function renderStatusDonut(containerEl, byStatus) {
    if (!containerEl) return;
    var counts = byStatus && typeof byStatus === "object" ? byStatus : {};
    var items = STATUS_SPECS.map(function (spec) {
      return {
        key: spec.key,
        label: spec.label,
        color: spec.color,
        count: toCount(counts[spec.key])
      };
    });
    var total = items.reduce(function (sum, item) {
      return sum + item.count;
    }, 0);

    var r = 50;
    var cx = 68;
    var cy = 68;
    var circumference = 2 * Math.PI * r;
    var offset = 0;
    var arcsHtml = "";

    if (total === 0) {
      arcsHtml =
        '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" ' +
        'fill="none" class="chart-track-ring" stroke-width="14" stroke-dasharray="4 4"></circle>';
    } else {
      items.forEach(function (item) {
        if (item.count <= 0) return;
        var ratio = item.count / total;
        var len = ratio * circumference;
        var gap = items.filter(function (x) { return x.count > 0; }).length > 1 ? Math.min(2.2, len * 0.15) : 0;
        var visibleLen = Math.max(0.5, len - gap);
        arcsHtml +=
          '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" ' +
          'fill="none" stroke="' + item.color + '" stroke-width="14" ' +
          'stroke-dasharray="' + visibleLen.toFixed(2) + ' ' + circumference.toFixed(2) + '" ' +
          'stroke-dashoffset="' + (-offset).toFixed(2) + '" ' +
          'stroke-linecap="butt">' +
          '<title>' + escapeHtml(item.label + ": " + item.count) + "</title>" +
          "</circle>";
        offset += len;
      });
    }

    var ariaSummary = total === 0
      ? "No notifications recorded yet"
      : items.filter(function (i) { return i.count > 0; }).map(function (i) {
          return i.label + " " + i.count;
        }).join(", ");

    var legendHtml = items.map(function (item) {
      var pct = total > 0 ? Math.round((item.count / total) * 100) : 0;
      return (
        '<li class="chart-legend-row">' +
          '<span class="chart-legend-key">' +
            '<span class="chart-swatch" style="background:' + item.color + ';" aria-hidden="true"></span>' +
            '<span>' + escapeHtml(item.label) + "</span>" +
          "</span>" +
          '<span class="chart-legend-val">' +
            "<strong>" + item.count + "</strong>" +
            '<span class="chart-legend-pct">(' + pct + "%)</span>" +
          "</span>" +
        "</li>"
      );
    }).join("");

    containerEl.innerHTML =
      '<div class="donut-layout">' +
        '<div class="donut-svg-wrap">' +
          '<svg class="donut-svg" viewBox="0 0 136 136" role="img" aria-label="Status distribution: ' + escapeHtml(ariaSummary) + '">' +
            '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" class="chart-track-ring" stroke-width="14"></circle>' +
            '<g transform="rotate(-90 ' + cx + " " + cy + ')">' + arcsHtml + "</g>" +
            '<text x="' + cx + '" y="' + (cy - 2) + '" text-anchor="middle" class="donut-total-num">' + total + "</text>" +
            '<text x="' + cx + '" y="' + (cy + 15) + '" text-anchor="middle" class="donut-total-label">EVENTS</text>' +
          "</svg>" +
        "</div>" +
        '<ul class="chart-legend-list" aria-label="Status counts">' + legendHtml + "</ul>" +
      "</div>";
  }

  function renderChannelBars(containerEl, byChannel) {
    if (!containerEl) return;
    var counts = byChannel && typeof byChannel === "object" ? byChannel : {};
    var rows = CHANNEL_SPECS.map(function (spec) {
      return {
        key: spec.key,
        label: spec.label,
        color: spec.color,
        count: toCount(counts[spec.key])
      };
    });

    var total = rows.reduce(function (sum, row) { return sum + row.count; }, 0);
    var maxVal = rows.reduce(function (m, row) { return Math.max(m, row.count); }, 1);

    var svgWidth = 360;
    var rowHeight = 36;
    var svgHeight = rows.length * rowHeight + 8;
    var labelW = 78;
    var valW = 44;
    var trackW = svgWidth - labelW - valW - 12;

    var barsSvg = rows.map(function (row, idx) {
      var y = idx * rowHeight + 8;
      var fillW = total === 0 ? 0 : Math.max(row.count > 0 ? 6 : 0, (row.count / maxVal) * trackW);
      return (
        '<g class="bar-row">' +
          '<text x="0" y="' + (y + 17) + '" class="svg-label-text">' + escapeHtml(row.label) + "</text>" +
          '<rect x="' + labelW + '" y="' + (y + 4) + '" width="' + trackW + '" height="18" rx="5" class="svg-bar-track"></rect>' +
          '<rect x="' + labelW + '" y="' + (y + 4) + '" width="' + fillW.toFixed(1) + '" height="18" rx="5" fill="' + row.color + '">' +
            '<title>' + escapeHtml(row.label + ": " + row.count + " dispatches") + "</title>" +
          "</rect>" +
          '<text x="' + (svgWidth - 4) + '" y="' + (y + 17) + '" text-anchor="end" class="svg-val-text">' + row.count + "</text>" +
        "</g>"
      );
    }).join("");

    var summaryText = rows.map(function (r) { return r.label + " " + r.count; }).join(", ");
    var emptyNote = total === 0 ? '<p class="chart-empty-hint">No channel dispatches logged yet.</p>' : "";

    containerEl.innerHTML =
      '<div class="bars-layout">' +
        '<svg class="bars-svg" viewBox="0 0 ' + svgWidth + " " + svgHeight + '" role="img" aria-label="Channel dispatch counts: ' + escapeHtml(summaryText) + '">' +
          barsSvg +
        "</svg>" +
        emptyNote +
        '<div class="sr-only">' + escapeHtml(summaryText) + "</div>" +
      "</div>";
  }

  function renderLatencySparkline(containerEl, samples) {
    if (!containerEl) return;
    var list = Array.isArray(samples) ? samples.filter(function (s) {
      return s && Number.isFinite(Number(s.ms)) && Number(s.ms) >= 0;
    }) : [];

    if (list.length > 30) {
      list = list.slice(list.length - 30);
    }

    if (list.length === 0) {
      containerEl.innerHTML =
        '<div class="sparkline-layout">' +
          '<div class="sparkline-stats">' +
            '<span class="mini-stat"><span>Min</span><strong>--</strong></span>' +
            '<span class="mini-stat"><span>Avg</span><strong>--</strong></span>' +
            '<span class="mini-stat"><span>Max</span><strong>--</strong></span>' +
            '<span class="mini-stat"><span>Last</span><strong>--</strong></span>' +
          "</div>" +
          '<svg class="sparkline-svg" viewBox="0 0 360 104" role="img" aria-label="API round-trip latency sparkline waiting for samples">' +
            '<line x1="12" y1="54" x2="348" y2="54" class="svg-avg-line"></line>' +
            '<text x="180" y="46" text-anchor="middle" class="svg-muted-text">Waiting for telemetry samples</text>' +
          "</svg>" +
        "</div>";
      return;
    }

    var values = list.map(function (s) { return Math.round(Number(s.ms)); });
    var minMs = Math.min.apply(null, values);
    var maxMs = Math.max.apply(null, values);
    var avgMs = Math.round(values.reduce(function (a, b) { return a + b; }, 0) / values.length);
    var lastMs = values[values.length - 1];

    var w = 360;
    var h = 104;
    var padX = 14;
    var padTop = 14;
    var padBottom = 18;
    var plotW = w - padX * 2;
    var plotH = h - padTop - padBottom;
    var ceilVal = Math.max(10, maxMs * 1.15);

    var points = list.map(function (s, idx) {
      var val = Number(s.ms);
      var x = list.length === 1 ? w / 2 : padX + (idx / (list.length - 1)) * plotW;
      var y = padTop + plotH - (val / ceilVal) * plotH;
      return {
        x: Number(x.toFixed(1)),
        y: Number(y.toFixed(1)),
        ms: Math.round(val),
        ok: s.ok !== false,
        label: s.label || ("Sample " + (idx + 1))
      };
    });

    var avgY = (padTop + plotH - (avgMs / ceilVal) * plotH).toFixed(1);
    var polylinePoints = points.map(function (p) { return p.x + "," + p.y; }).join(" ");
    var areaPath = "";
    if (points.length > 1) {
      areaPath =
        "M " + points[0].x + " " + (padTop + plotH) + " " +
        points.map(function (p) { return "L " + p.x + " " + p.y; }).join(" ") +
        " L " + points[points.length - 1].x + " " + (padTop + plotH) + " Z";
    }

    var dotsSvg = points.map(function (p, idx) {
      var isLast = idx === points.length - 1;
      var color = p.ok ? "#38BDF8" : "#EF4444";
      var radius = isLast ? 4 : (!p.ok ? 3.5 : 2.3);
      return (
        '<circle cx="' + p.x + '" cy="' + p.y + '" r="' + radius + '" fill="' + color + '" class="spark-dot">' +
          "<title>" + escapeHtml(p.label + ": " + p.ms + " ms" + (p.ok ? "" : " (error)")) + "</title>" +
        "</circle>"
      );
    }).join("");

    var ariaMsg = "API RTT over " + points.length + " samples: min " + minMs + "ms, avg " + avgMs + "ms, max " + maxMs + "ms, latest " + lastMs + "ms";

    containerEl.innerHTML =
      '<div class="sparkline-layout">' +
        '<div class="sparkline-stats">' +
          '<span class="mini-stat"><span>Min</span><strong>' + minMs + " ms</strong></span>" +
          '<span class="mini-stat"><span>Avg</span><strong>' + avgMs + " ms</strong></span>" +
          '<span class="mini-stat"><span>Max</span><strong>' + maxMs + " ms</strong></span>" +
          '<span class="mini-stat"><span>Last</span><strong>' + lastMs + " ms</strong></span>" +
        "</div>" +
        '<svg class="sparkline-svg" viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="' + escapeHtml(ariaMsg) + '">' +
          '<line x1="' + padX + '" y1="' + avgY + '" x2="' + (w - padX) + '" y2="' + avgY + '" class="svg-avg-line"></line>' +
          (areaPath ? '<path d="' + areaPath + '" class="spark-area"></path>' : "") +
          (points.length > 1 ? '<polyline points="' + polylinePoints + '" fill="none" stroke="#38BDF8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"></polyline>' : "") +
          dotsSvg +
          '<text x="' + padX + '" y="' + (h - 4) + '" class="svg-muted-text">0 ms</text>' +
          '<text x="' + (w - padX) + '" y="' + (h - 4) + '" text-anchor="end" class="svg-muted-text">avg ' + avgMs + " ms</text>" +
        "</svg>" +
      "</div>";
  }

  function _normalizeStatusClass(status) {
    var s = String(status || "ok").toLowerCase();
    if (s === "failed" || s === "error" || s === "dlq" || s === "401" || s === "422" || s === "400" || s === "409" || s === "503") {
      return "state-error";
    }
    if (s === "retrying" || s === "warn" || s === "warning") {
      return "state-warn";
    }
    if (s === "duplicate_ignored" || s === "suppressed" || s === "info") {
      return "state-suppressed";
    }
    if (s === "idle") {
      return "state-idle";
    }
    return "state-ok";
  }

  function _ensurePipelineMarkup(containerEl) {
    if (containerEl.querySelector("[data-stage]")) return;
    var mainTrack = PIPELINE_STAGES.map(function (st, idx) {
      var arrow = idx < PIPELINE_STAGES.length - 1
        ? '<span class="pipe-connector" data-connector="' + st.key + '" aria-hidden="true">' +
            '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>' +
          "</span>"
        : "";
      return (
        '<div class="pipe-node" data-stage="' + st.key + '">' +
          '<span class="pipe-title">' + escapeHtml(st.title) + "</span>" +
          '<span class="pipe-sub">' + escapeHtml(st.subtitle) + "</span>" +
        "</div>" + arrow
      );
    }).join("");

    containerEl.innerHTML =
      '<div class="pipeline-track">' + mainTrack + "</div>" +
      '<div class="pipeline-dlq-row">' +
        '<span class="pipe-branch-label">DLQ Branch</span>' +
        '<div class="pipe-node pipe-node-dlq" data-stage="dlq">' +
          '<span class="pipe-title">Dead-Letter Queue</span>' +
          '<span class="pipe-sub">campus.alerts.dlq</span>' +
        "</div>" +
      "</div>";
  }

  function pulsePipeline(containerEl, activeStages, status) {
    if (!containerEl) return;
    _ensurePipelineMarkup(containerEl);

    var stageSet = {};
    if (activeStages === "all") {
      ["core", "mqtt", "validator", "store", "delivery"].forEach(function (k) { stageSet[k] = true; });
    } else if (Array.isArray(activeStages)) {
      activeStages.forEach(function (k) { stageSet[String(k)] = true; });
    } else if (activeStages && typeof activeStages.forEach === "function") {
      activeStages.forEach(function (k) { stageSet[String(k)] = true; });
    }

    var stateClass = _normalizeStatusClass(status);
    var stageNodes = containerEl.querySelectorAll("[data-stage]");
    for (var i = 0; i < stageNodes.length; i++) {
      var node = stageNodes[i];
      var key = node.getAttribute("data-stage");
      node.classList.remove("is-active", "state-ok", "state-warn", "state-error", "state-suppressed", "state-idle");
      if (stageSet[key]) {
        node.classList.add("is-active", key === "dlq" ? "state-error" : stateClass);
      }
    }

    var connectors = containerEl.querySelectorAll("[data-connector]");
    for (var j = 0; j < connectors.length; j++) {
      var conn = connectors[j];
      var connKey = conn.getAttribute("data-connector");
      conn.classList.remove("is-active", "state-ok", "state-warn", "state-error", "state-suppressed");
      if (stageSet[connKey]) {
        conn.classList.add("is-active", stateClass);
      }
    }
  }

  global.DemoCharts = {
    renderStatusDonut: renderStatusDonut,
    renderChannelBars: renderChannelBars,
    renderLatencySparkline: renderLatencySparkline,
    pulsePipeline: pulsePipeline
  };
})(window);
