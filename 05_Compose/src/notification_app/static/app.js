/**
 * Smart Campus Notification Service — Control Center Application Logic
 * Wires all 5 operational tabs, live polling, theme/auth persistence,
 * scenario execution, accessible validation, DLQ fault recovery, and 7-API tester.
 */
(function (global, doc) {
  "use strict";

  var STORAGE_TOKEN_KEY = "sc_notify_token";
  var STORAGE_THEME_KEY = "sc_notify_theme";
  var UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  var ALERT_ID_RE = /^ALT-[0-9]{3,}$/;
  var ISO_TZ_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

  var DS = global.DemoScenarios;
  var DC = global.DemoCharts;

  var state = {
    token: "",
    config: null,
    mqttConnected: false,
    theme: "dark",
    activeTab: "overview",
    polling: {
      paused: false,
      intervalMs: 5000,
      timerId: null,
      inFlight: false,
      autoPausedByHidden: false
    },
    latencySamples: [],
    recentNotifications: [],
    latestNotificationId: "",
    lastFailedNotificationId: "",
    explorer: {
      cursorStack: [],
      currentCursor: null,
      nextCursor: null,
      hasMore: false,
      items: [],
      filters: {
        alert_id: "",
        status: "",
        channel: "",
        limit: 20
      }
    },
    faults: {
      fail_channels: [],
      max_retries_override: null,
      retry_interval_override: null,
      effective_max_retries: 3,
      effective_retry_interval_seconds: 5
    },
    dlqItems: [],
    highlightedDlqIndex: -1,
    deliveryFeed: [],
    feedFilterChannel: "all",
    apiTester: {
      selectedId: "getHealth",
      inputsById: {},
      sendWithoutAuth: false
    },
    drawer: {
      open: false,
      notificationId: null,
      lastFocusEl: null,
      currentRecord: null
    }
  };

  function $(id) {
    return doc.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function safeReadStorage(key) {
    try {
      return global.localStorage ? global.localStorage.getItem(key) : null;
    } catch (_) {
      return null;
    }
  }

  function safeWriteStorage(key, value) {
    try {
      if (!global.localStorage) return;
      if (value === null || value === undefined || value === "") {
        global.localStorage.removeItem(key);
      } else {
        global.localStorage.setItem(key, String(value));
      }
    } catch (_) {
      // Ignore storage quota / privacy mode restrictions
    }
  }

  function formatUtcTime(isoStr) {
    if (!isoStr) return "--";
    var str = String(isoStr);
    if (str.length >= 19 && str.indexOf("T") !== -1) {
      return str.slice(0, 19).replace("T", " ");
    }
    return str;
  }

  function formatLocalClock(dateObj) {
    var d = dateObj || new Date();
    var hh = String(d.getHours()).padStart(2, "0");
    var mm = String(d.getMinutes()).padStart(2, "0");
    var ss = String(d.getSeconds()).padStart(2, "0");
    return hh + ":" + mm + ":" + ss;
  }

  function shortId(id) {
    if (!id) return "--";
    var s = String(id);
    return s.length > 13 ? s.slice(0, 8) + "..." + s.slice(-4) : s;
  }

  function showToast(title, message, tone) {
    var region = $("toast-region");
    if (!region) return;
    var kind = tone || "info";
    var item = doc.createElement("div");
    item.className = "toast-item toast-" + kind;

    var copy = doc.createElement("div");
    var strong = doc.createElement("strong");
    strong.textContent = title || "Notification";
    var body = doc.createElement("div");
    body.textContent = message || "";
    body.style.fontSize = "0.79rem";
    body.style.marginTop = "2px";
    body.style.color = "var(--muted)";
    copy.appendChild(strong);
    if (message) copy.appendChild(body);

    var closeBtn = doc.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "btn btn-ghost btn-sm";
    closeBtn.setAttribute("aria-label", "Dismiss notification");
    closeBtn.textContent = "x";
    closeBtn.addEventListener("click", function () {
      if (item.parentNode) item.parentNode.removeChild(item);
    });

    item.appendChild(copy);
    item.appendChild(closeBtn);
    region.appendChild(item);

    while (region.children.length > 4) {
      region.removeChild(region.firstChild);
    }

    global.setTimeout(function () {
      if (item.parentNode) item.parentNode.removeChild(item);
    }, 5500);
  }

  function recordLatency(label, ms, ok) {
    state.latencySamples.push({
      label: label,
      ms: Math.max(0, Math.round(ms)),
      ok: Boolean(ok)
    });
    if (state.latencySamples.length > 30) {
      state.latencySamples = state.latencySamples.slice(state.latencySamples.length - 30);
    }
    var chartEl = $("chart-latency");
    if (chartEl && DC && typeof DC.renderLatencySparkline === "function") {
      DC.renderLatencySparkline(chartEl, state.latencySamples);
    }
  }

  var authBannerTimer = null;

  function setAuthBanner(message, mode) {
    var banner = $("auth-status-banner");
    if (!banner) return;
    if (authBannerTimer) {
      global.clearTimeout(authBannerTimer);
      authBannerTimer = null;
    }
    banner.classList.remove("is-error", "is-ok");
    if (!message) {
      banner.hidden = true;
      banner.textContent = "";
      return;
    }
    if (mode === "error") banner.classList.add("is-error");
    if (mode === "ok") banner.classList.add("is-ok");
    banner.textContent = message;
    banner.hidden = false;
  }

  function setStatusPill(el, level, text) {
    if (!el) return;
    el.classList.remove("status-ok", "status-warning", "status-danger", "status-neutral", "is-ok", "is-warn", "is-error");
    el.classList.add(level);
    var span = el.querySelector("span");
    if (span) {
      span.textContent = text;
    }
  }

  async function apiFetch(path, options) {
    var opts = options || {};
    var method = (opts.method || "GET").toUpperCase();
    var headers = Object.assign({}, opts.headers || {});
    var authMode = opts.authMode || "default";

    if (authMode === "default" && state.token && !headers.Authorization) {
      headers.Authorization = "Bearer " + state.token;
    } else if (authMode === "override" && opts.overrideToken) {
      headers.Authorization = "Bearer " + opts.overrideToken;
    } else if (authMode === "none") {
      delete headers.Authorization;
    }

    var fetchOpts = {
      method: method,
      headers: headers,
      cache: "no-store"
    };

    if (opts.rawBody !== undefined && opts.rawBody !== null) {
      if (!headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
      }
      fetchOpts.body = opts.rawBody;
    } else if (opts.body !== undefined && opts.body !== null) {
      if (!headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
      }
      fetchOpts.body = JSON.stringify(opts.body);
    }

    var started = global.performance && typeof global.performance.now === "function"
      ? global.performance.now()
      : Date.now();

    try {
      var resp = await global.fetch(path, fetchOpts);
      var ended = global.performance && typeof global.performance.now === "function"
        ? global.performance.now()
        : Date.now();
      var rttMs = Math.max(0, Math.round(ended - started));

      if (opts.recordLatency !== false) {
        recordLatency(method + " " + path.split("?")[0], rttMs, resp.ok);
      }

      var rawText = await resp.text();
      var parsed = null;
      if (rawText) {
        try {
          parsed = JSON.parse(rawText);
        } catch (_) {
          parsed = rawText;
        }
      }

      var respHeaders = {};
      resp.headers.forEach(function (val, key) {
        respHeaders[key] = val;
      });

      if (resp.status === 401 && authMode === "default") {
        setAuthBanner("Unauthorized (401): apply valid AUTH_TOKEN or Use Dev Token", "error");
      }

      return {
        ok: resp.ok,
        status: resp.status,
        statusText: resp.statusText,
        ms: rttMs,
        headers: respHeaders,
        data: parsed,
        rawText: rawText,
        networkError: null
      };
    } catch (err) {
      var failedEnd = global.performance && typeof global.performance.now === "function"
        ? global.performance.now()
        : Date.now();
      var failMs = Math.max(0, Math.round(failedEnd - started));
      if (opts.recordLatency !== false) {
        recordLatency(method + " " + path.split("?")[0], failMs, false);
      }
      return {
        ok: false,
        status: 0,
        statusText: "Network Error",
        ms: failMs,
        headers: {},
        data: { error: err && err.message ? err.message : "Network request failed" },
        rawText: "",
        networkError: err && err.message ? err.message : "Network request failed"
      };
    }
  }

  function renderChannelChipsHtml(channels) {
    if (!Array.isArray(channels) || channels.length === 0) {
      return '<span class="badge badge-neutral">none</span>';
    }
    return (
      '<div class="channel-chip-row">' +
      channels
        .map(function (ch) {
          var clean = String(ch || "").toLowerCase();
          var cls = ["telegram", "email", "discord", "sms"].indexOf(clean) !== -1 ? "ch-" + clean : "";
          return '<span class="channel-chip ' + cls + '">' + escapeHtml(clean) + "</span>";
        })
        .join("") +
      "</div>"
    );
  }

  function renderStatusBadgeHtml(status) {
    var key = String(status || "queued");
    var meta = DS && DS.STATUS_META && DS.STATUS_META[key];
    var label = meta ? meta.label : key;
    var cls = meta ? meta.className : "status-" + escapeHtml(key);
    return '<span class="badge ' + escapeHtml(cls) + '">' + escapeHtml(label) + "</span>";
  }

  function renderSeverityBadgeHtml(severity) {
    if (!severity) {
      return '<span class="badge badge-neutral">none</span>';
    }
    var s = String(severity).toLowerCase();
    var known = ["low", "medium", "high", "critical"].indexOf(s) !== -1;
    return '<span class="sev-badge ' + (known ? "sev-" + s : "badge-neutral") + '">' + escapeHtml(s) + "</span>";
  }

  function renderResponseInspector(containerEl, res, titleLabel) {
    if (!containerEl) return;
    if (!res) {
      containerEl.innerHTML = '<div class="empty-inspector">No response captured yet.</div>';
      return;
    }

    var badgeClass = "badge-neutral";
    if (res.status >= 200 && res.status < 300) {
      badgeClass = "badge-success";
    } else if (res.status >= 400 && res.status < 500) {
      badgeClass = "badge-warning";
    } else if (res.status >= 500 || res.status === 0) {
      badgeClass = "badge-danger";
    }

    var statusText = res.status === 0 ? "NET ERR" : String(res.status) + " " + (res.statusText || "");
    var contentType = (res.headers && (res.headers["content-type"] || res.headers["Content-Type"])) || "application/json";
    var locationHdr = res.headers && (res.headers.location || res.headers.Location);
    var traceHdr = res.headers && (res.headers["x-trace-id"] || res.headers["X-Trace-Id"]);

    var formattedBody = typeof res.data === "string"
      ? res.data
      : JSON.stringify(res.data, null, 2);

    var headerMeta =
      '<div class="response-meta">' +
      (titleLabel ? '<span class="badge badge-info">' + escapeHtml(titleLabel) + "</span>" : "") +
      '<span class="badge ' + badgeClass + '">' + escapeHtml(statusText.trim()) + "</span>" +
      '<span class="badge badge-neutral mono">' + escapeHtml(String(res.ms || 0)) + " ms</span>" +
      '<span class="badge badge-neutral mono">' + escapeHtml(contentType.split(";")[0]) + "</span>" +
      (locationHdr ? '<span class="badge badge-info mono">Location: ' + escapeHtml(locationHdr) + "</span>" : "") +
      (traceHdr ? '<span class="badge badge-neutral mono">X-Trace-Id: ' + escapeHtml(traceHdr) + "</span>" : "") +
      "</div>";

    var problemBlock = "";
    if (res.data && typeof res.data === "object" && res.data.type && res.data.title && Array.isArray(res.data.errors) && res.data.errors.length > 0) {
      problemBlock =
        '<div style="margin-bottom:10px;padding:8px 10px;border-radius:8px;border:1px solid var(--warning-border);background:var(--warning-bg);font-size:0.79rem;">' +
        "<strong>RFC 9457 Field Errors:</strong>" +
        '<ul style="margin:5px 0 0;padding-left:18px;">' +
        res.data.errors
          .map(function (fe) {
            return (
              "<li><code>" +
              escapeHtml(fe.field || "field") +
              "</code> [<strong>" +
              escapeHtml(fe.code || "ERR") +
              "</strong>]: " +
              escapeHtml(fe.message || "") +
              "</li>"
            );
          })
          .join("") +
        "</ul></div>";
    }

    containerEl.innerHTML =
      headerMeta +
      problemBlock +
      '<pre class="response-pre mono">' +
      escapeHtml(formattedBody || "(empty body)") +
      "</pre>";
  }

  // ------------------------------------------------------------------ Theme
  function applyTheme(theme) {
    var next = theme === "light" ? "light" : "dark";
    state.theme = next;
    doc.documentElement.setAttribute("data-theme", next);
    safeWriteStorage(STORAGE_THEME_KEY, next);

    var btn = $("btn-theme-toggle");
    if (btn) {
      btn.setAttribute(
        "aria-label",
        next === "dark" ? "Switch to light theme" : "Switch to dark theme"
      );
      btn.setAttribute("title", next === "dark" ? "Switch to light theme" : "Switch to dark theme");
      btn.innerHTML =
        next === "dark"
          ? '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path></svg>'
          : '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>';
    }
  }

  function initTheme() {
    var saved = safeReadStorage(STORAGE_THEME_KEY);
    applyTheme(saved === "light" ? "light" : "dark");
    var btn = $("btn-theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        applyTheme(state.theme === "dark" ? "light" : "dark");
      });
    }
  }

  // ------------------------------------------------------------------ Tabs
  function switchTab(tabName) {
    var tabs = doc.querySelectorAll('[role="tab"][data-tab]');
    var valid = false;
    for (var i = 0; i < tabs.length; i += 1) {
      if (tabs[i].getAttribute("data-tab") === tabName) {
        valid = true;
        break;
      }
    }
    if (!valid) return;
    state.activeTab = tabName;

    for (var j = 0; j < tabs.length; j += 1) {
      var btn = tabs[j];
      var isCurrent = btn.getAttribute("data-tab") === tabName;
      btn.classList.toggle("is-active", isCurrent);
      btn.setAttribute("aria-selected", isCurrent ? "true" : "false");
    }

    var panels = doc.querySelectorAll(".tab-panel");
    for (var k = 0; k < panels.length; k += 1) {
      var panel = panels[k];
      panel.hidden = panel.id !== "panel-" + tabName;
    }

    if (tabName === "explorer") {
      refreshExplorer();
    } else if (tabName === "faults") {
      refreshFaultsAndDlq();
    } else if (tabName === "channels") {
      refreshDeliveryFeed();
      renderApiTesterGrid();
    } else if (tabName === "overview") {
      refreshOverviewAndRecent();
    }
  }

  function initTabs() {
    var tabList = doc.querySelector('[role="tablist"]');
    var tabs = Array.prototype.slice.call(doc.querySelectorAll('[role="tab"][data-tab]'));
    tabs.forEach(function (tab, index) {
      tab.addEventListener("click", function () {
        switchTab(tab.getAttribute("data-tab"));
      });
      tab.addEventListener("keydown", function (ev) {
        var nextIndex = -1;
        if (ev.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
        else if (ev.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
        else if (ev.key === "Home") nextIndex = 0;
        else if (ev.key === "End") nextIndex = tabs.length - 1;
        if (nextIndex !== -1) {
          ev.preventDefault();
          tabs[nextIndex].focus();
          switchTab(tabs[nextIndex].getAttribute("data-tab"));
        }
      });
    });
    if (tabList && !state.activeTab) {
      switchTab("overview");
    }
  }

  // ------------------------------------------------------------------ Config, Auth & Health
  async function loadConfigAndAuth() {
    var res = await apiFetch("/demo-api/config", { authMode: "none" });
    var savedToken = safeReadStorage(STORAGE_TOKEN_KEY) || "";
    var tokenInput = $("auth-token-input");
    var devBtn = $("btn-use-dev-token");

    if (res.ok && res.data && typeof res.data === "object") {
      state.config = res.data;
      if (devBtn) {
        devBtn.disabled = !res.data.dev_token_hint;
        if (!res.data.dev_token_hint) {
          devBtn.title = "Dev token hint disabled for custom ENV / AUTH_TOKEN";
        }
      }
      if (savedToken) {
        state.token = savedToken;
        if (tokenInput) tokenInput.value = savedToken;
        setAuthBanner("", "");
      } else if (res.data.dev_token_hint) {
        state.token = res.data.dev_token_hint;
        if (tokenInput) tokenInput.value = res.data.dev_token_hint;
        setAuthBanner("", "");
      } else {
        state.token = "";
        setAuthBanner("Bearer AUTH_TOKEN required for protected APIs", "error");
      }
    } else {
      if (savedToken) {
        state.token = savedToken;
        if (tokenInput) tokenInput.value = savedToken;
      }
      if (devBtn) devBtn.disabled = true;
    }
  }

  function initAuthControls() {
    var tokenInput = $("auth-token-input");
    var btnUseDev = $("btn-use-dev-token");
    var btnApply = $("btn-auth-apply");

    if (btnUseDev) {
      btnUseDev.addEventListener("click", function () {
        if (!state.config || !state.config.dev_token_hint) {
          setAuthBanner("Dev token hint unavailable in this environment", "error");
          return;
        }
        state.token = state.config.dev_token_hint;
        if (tokenInput) tokenInput.value = state.token;
        safeWriteStorage(STORAGE_TOKEN_KEY, state.token);
        setAuthBanner("Dev token applied", "ok");
        authBannerTimer = global.setTimeout(function () {
          var b = $("auth-status-banner");
          if (b && b.classList.contains("is-ok")) setAuthBanner("", "");
        }, 2500);
        refreshAll();
      });
    }

    function applyManualToken() {
      var val = tokenInput ? tokenInput.value.trim() : "";
      state.token = val;
      safeWriteStorage(STORAGE_TOKEN_KEY, val);
      if (!val) {
        setAuthBanner("Bearer token cleared — protected endpoints will return 401", "error");
      } else {
        setAuthBanner("Token applied", "ok");
        authBannerTimer = global.setTimeout(function () {
          var b = $("auth-status-banner");
          if (b && b.classList.contains("is-ok")) setAuthBanner("", "");
        }, 2200);
      }
      refreshAll();
    }

    if (btnApply) {
      btnApply.addEventListener("click", applyManualToken);
    }
    if (tokenInput) {
      tokenInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          applyManualToken();
        }
      });
    }
  }

  async function refreshHealthAndReadiness() {
    var healthPill = $("status-health");
    var dbPill = $("status-db");
    var mqttPill = $("status-mqtt");

    var results = await Promise.all([
      apiFetch("/health", { authMode: "none" }),
      apiFetch("/ready", { authMode: "none" })
    ]);
    var hRes = results[0];
    var rRes = results[1];

    if (hRes.networkError) {
      setStatusPill(healthPill, "status-danger", "Health: Offline");
    } else if (hRes.ok && hRes.data && hRes.data.status === "ok") {
      setStatusPill(healthPill, "status-ok", "Health: OK");
    } else {
      setStatusPill(healthPill, "status-danger", "Health: " + hRes.status);
    }

    if (rRes.networkError || !rRes.data || !rRes.data.dependencies) {
      setStatusPill(dbPill, "status-danger", "DB: Unreachable");
      setStatusPill(mqttPill, "status-danger", "MQTT: Unreachable");
      state.mqttConnected = false;
      return false;
    }

    var deps = rRes.data.dependencies;
    var db = deps.database || {};
    var mqtt = deps.mqtt || {};

    if (db.ready) {
      setStatusPill(dbPill, "status-ok", "DB: " + (db.backend || "ready"));
    } else {
      setStatusPill(dbPill, "status-danger", "DB: Degraded");
    }

    state.mqttConnected = Boolean(mqtt.enabled && mqtt.connected);
    if (!mqtt.enabled) {
      setStatusPill(mqttPill, "status-neutral", "MQTT: Disabled (REST)");
    } else if (mqtt.connected) {
      setStatusPill(mqttPill, "status-ok", "MQTT: Connected");
    } else {
      setStatusPill(mqttPill, "status-warning", "MQTT: Disconnected");
    }

    return true;
  }

  // ------------------------------------------------------------------ Overview & Polling
  function updateFaultIndicators(activeFaults) {
    if (!activeFaults || typeof activeFaults !== "object") return;
    state.faults = activeFaults;

    var failChannels = Array.isArray(activeFaults.fail_channels) ? activeFaults.fail_channels : [];
    var hasOverride =
      failChannels.length > 0 ||
      activeFaults.max_retries_override !== null ||
      activeFaults.retry_interval_override !== null;

    var topBanner = $("status-fault-banner");
    if (topBanner) {
      topBanner.hidden = !hasOverride;
      if (hasOverride) {
        var parts = [];
        if (failChannels.length > 0) parts.push("FAIL=" + failChannels.join(","));
        if (activeFaults.max_retries_override !== null) {
          parts.push("MAX_RETRIES=" + activeFaults.max_retries_override);
        }
        if (activeFaults.retry_interval_override !== null) {
          parts.push("INTERVAL=" + activeFaults.retry_interval_override + "s");
        }
        var span = topBanner.querySelector("span");
        if (span) span.textContent = "Fault Active (" + parts.join(" · ") + ")";
      }
    }

    var summaryBox = $("fault-active-summary");
    if (summaryBox) {
      summaryBox.classList.toggle("is-fault-active", hasOverride);
      summaryBox.textContent = hasOverride
        ? "ACTIVE FAULT OVERRIDES — fail_channels: [" +
          (failChannels.join(", ") || "none") +
          "], effective max_retries: " +
          activeFaults.effective_max_retries +
          ", retry_interval: " +
          activeFaults.effective_retry_interval_seconds +
          "s."
        : "No active fault overrides (effective max_retries: " +
          activeFaults.effective_max_retries +
          ", interval: " +
          activeFaults.effective_retry_interval_seconds +
          "s).";
    }

    var channelBoxes = doc.querySelectorAll("[data-fault-channel]");
    for (var i = 0; i < channelBoxes.length; i += 1) {
      var cb = channelBoxes[i];
      var ch = cb.getAttribute("data-fault-channel");
      cb.checked = failChannels.indexOf(ch) !== -1;
    }

    var maxRetriesInput = $("fault-max-retries");
    if (maxRetriesInput && doc.activeElement !== maxRetriesInput) {
      maxRetriesInput.value =
        activeFaults.max_retries_override !== null && activeFaults.max_retries_override !== undefined
          ? String(activeFaults.max_retries_override)
          : "";
    }
    var intervalInput = $("fault-retry-interval");
    if (intervalInput && doc.activeElement !== intervalInput) {
      intervalInput.value =
        activeFaults.retry_interval_override !== null && activeFaults.retry_interval_override !== undefined
          ? String(activeFaults.retry_interval_override)
          : "";
    }
  }

  function renderOverviewRecentTable(items) {
    var tbody = $("overview-recent-body");
    if (!tbody) return;

    if (!Array.isArray(items) || items.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="8" class="table-empty">No notification records logged yet. Run a scenario in Simulator.</td></tr>';
      return;
    }

    tbody.innerHTML = items
      .map(function (item) {
        var nid = item.notification_id || "";
        return (
          '<tr class="is-clickable" data-nid="' +
          escapeHtml(nid) +
          '">' +
          '<td class="mono">' +
          escapeHtml(formatUtcTime(item.created_at)) +
          "</td>" +
          '<td class="mono"><strong>' +
          escapeHtml(item.alert_id || "--") +
          "</strong></td>" +
          "<td><code>" +
          escapeHtml(item.event_name || "--") +
          "</code></td>" +
          "<td>" +
          renderSeverityBadgeHtml(item.severity) +
          "</td>" +
          "<td>" +
          renderChannelChipsHtml(item.target_channels) +
          "</td>" +
          "<td>" +
          renderStatusBadgeHtml(item.status) +
          "</td>" +
          '<td class="mono">' +
          escapeHtml(String(item.retry_count != null ? item.retry_count : 0)) +
          "</td>" +
          '<td><button type="button" class="btn btn-ghost btn-sm" data-open-detail="' +
          escapeHtml(nid) +
          '">Inspect</button></td>' +
          "</tr>"
        );
      })
      .join("");
  }

  function pulsePipelineFromOverview(overview, recentItems) {
    var pipeEl = $("pipeline-visualizer");
    if (!pipeEl || !DC || typeof DC.pulsePipeline !== "function") return;

    var latest = Array.isArray(recentItems) && recentItems.length > 0 ? recentItems[0] : null;
    if (!latest) {
      DC.pulsePipeline(pipeEl, ["core", "mqtt", "validator", "store", "delivery"], "ok");
      return;
    }
    var st = latest.status || "delivered";
    if (st === "failed") {
      DC.pulsePipeline(pipeEl, ["core", "mqtt", "validator", "store", "delivery", "dlq"], "failed");
    } else if (st === "duplicate_ignored") {
      DC.pulsePipeline(pipeEl, ["core", "mqtt", "validator", "store"], "duplicate_ignored");
    } else if (st === "retrying") {
      DC.pulsePipeline(pipeEl, ["core", "mqtt", "validator", "store", "delivery"], "retrying");
    } else {
      DC.pulsePipeline(pipeEl, ["core", "mqtt", "validator", "store", "delivery"], "ok");
    }
  }

  async function refreshOverviewAndRecent() {
    if (!state.token) {
      renderOverviewRecentTable([]);
      return false;
    }

    var results = await Promise.all([
      apiFetch("/demo-api/overview"),
      apiFetch("/notifications/recent?limit=6")
    ]);
    var ovRes = results[0];
    var recRes = results[1];

    if (ovRes.ok && ovRes.data) {
      var banner = $("auth-status-banner");
      if (banner && banner.classList.contains("is-error")) {
        setAuthBanner("", "");
      }
      var ov = ovRes.data;
      var byStatus = ov.by_status || {};
      var setNum = function (id, val) {
        var el = $(id);
        if (el) el.textContent = String(Number(val) || 0);
      };
      setNum("kpi-total", ov.total);
      setNum("kpi-delivered", byStatus.delivered);
      setNum("kpi-retrying", byStatus.retrying);
      setNum("kpi-failed", byStatus.failed);
      setNum("kpi-suppressed", byStatus.duplicate_ignored);

      if (DC) {
        DC.renderStatusDonut($("chart-status-donut"), byStatus);
        DC.renderChannelBars($("chart-channel-bars"), ov.by_channel || {});
      }

      var dlqBadge = $("dlq-count-badge");
      if (dlqBadge && ov.dlq_count !== undefined) {
        dlqBadge.textContent = String(ov.dlq_count);
      }

      if (ov.active_faults) {
        updateFaultIndicators(ov.active_faults);
      }
    }

    if (recRes.ok && recRes.data && Array.isArray(recRes.data.items)) {
      state.recentNotifications = recRes.data.items;
      if (recRes.data.items.length > 0) {
        state.latestNotificationId = recRes.data.items[0].notification_id || state.latestNotificationId;
        for (var i = 0; i < recRes.data.items.length; i += 1) {
          if (recRes.data.items[i].status === "failed") {
            state.lastFailedNotificationId = recRes.data.items[i].notification_id;
            break;
          }
        }
      }
      renderOverviewRecentTable(recRes.data.items);
      updateComposerRoutingPreview();
      if (ovRes.ok && ovRes.data) {
        pulsePipelineFromOverview(ovRes.data, recRes.data.items);
      }
    }

    return !ovRes.networkError && !recRes.networkError;
  }

  async function refreshAll() {
    if (state.polling.inFlight) return;
    state.polling.inFlight = true;
    var labelEl = $("last-updated-label");
    try {
      var netOk = await refreshHealthAndReadiness();
      var ovOk = await refreshOverviewAndRecent();

      if (state.activeTab === "explorer") {
        await refreshExplorer();
      } else if (state.activeTab === "faults") {
        await refreshFaultsAndDlq();
      } else if (state.activeTab === "channels") {
        await refreshDeliveryFeed();
      }

      if (labelEl) {
        if (!netOk || (state.token && !ovOk)) {
          labelEl.textContent = "Stale · connection error";
          labelEl.style.color = "var(--warning-text)";
        } else {
          labelEl.style.color = "";
          labelEl.textContent = state.polling.paused
            ? "Paused · " + formatLocalClock()
            : "Synced " + formatLocalClock();
        }
      }
    } finally {
      state.polling.inFlight = false;
    }
  }

  function schedulePollTimer() {
    if (state.polling.timerId) {
      global.clearInterval(state.polling.timerId);
      state.polling.timerId = null;
    }
    if (state.polling.paused || doc.hidden) return;
    state.polling.timerId = global.setInterval(function () {
      if (!doc.hidden && !state.polling.paused) {
        refreshAll();
      }
    }, state.polling.intervalMs);
  }

  function updatePollButtonUi() {
    var btn = $("btn-poll-toggle");
    if (!btn) return;
    btn.setAttribute("aria-pressed", state.polling.paused ? "true" : "false");
    btn.innerHTML = state.polling.paused
      ? '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg><span>Resume</span>'
      : '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg><span>Pause</span>';
  }

  function initPolling() {
    var toggleBtn = $("btn-poll-toggle");
    var intervalSelect = $("poll-interval");

    if (toggleBtn) {
      toggleBtn.addEventListener("click", function () {
        state.polling.paused = !state.polling.paused;
        state.polling.autoPausedByHidden = false;
        updatePollButtonUi();
        var labelEl = $("last-updated-label");
        if (state.polling.paused) {
          if (state.polling.timerId) {
            global.clearInterval(state.polling.timerId);
            state.polling.timerId = null;
          }
          if (labelEl) labelEl.textContent = "Paused · " + formatLocalClock();
        } else {
          refreshAll();
          schedulePollTimer();
        }
      });
    }

    if (intervalSelect) {
      var parsed = parseInt(intervalSelect.value, 10);
      if (Number.isFinite(parsed) && parsed >= 1000) {
        state.polling.intervalMs = parsed;
      }
      intervalSelect.addEventListener("change", function () {
        var next = parseInt(intervalSelect.value, 10);
        if (Number.isFinite(next) && next >= 1000) {
          state.polling.intervalMs = next;
          schedulePollTimer();
        }
      });
    }

    doc.addEventListener("visibilitychange", function () {
      if (doc.hidden) {
        if (state.polling.timerId) {
          global.clearInterval(state.polling.timerId);
          state.polling.timerId = null;
        }
        if (!state.polling.paused) {
          state.polling.autoPausedByHidden = true;
        }
      } else {
        if (state.polling.autoPausedByHidden && !state.polling.paused) {
          state.polling.autoPausedByHidden = false;
          refreshAll();
          schedulePollTimer();
        }
      }
    });

    updatePollButtonUi();
    schedulePollTimer();
  }

  // ------------------------------------------------------------------ Detail Drawer
  function renderDrawerBody(record) {
    var bodyEl = $("detail-drawer-body");
    var titleEl = $("detail-drawer-title");
    var retryBtn = $("btn-drawer-retry");
    if (!bodyEl) return;

    if (titleEl) {
      titleEl.textContent = (record.alert_id || "Alert") + " · " + (record.event_name || "Notification");
    }

    if (retryBtn) {
      var blockedStatus = ["retrying", "queued", "duplicate_ignored"].indexOf(record.status) !== -1;
      retryBtn.disabled = blockedStatus;
      retryBtn.setAttribute("data-retry-id", record.notification_id || "");
    }

    var errorNotice = record.error_detail
      ? '<div style="padding:10px 12px;border-radius:8px;border:1px solid var(--danger-border);background:var(--danger-bg);color:var(--danger-text);font-size:0.82rem;"><strong>Error Detail:</strong> ' +
        escapeHtml(record.error_detail) +
        "</div>"
      : "";

    bodyEl.innerHTML =
      '<div class="drawer-kv-grid">' +
      '<div class="drawer-kv"><span>Status</span>' +
      renderStatusBadgeHtml(record.status) +
      "</div>" +
      '<div class="drawer-kv"><span>Severity</span>' +
      renderSeverityBadgeHtml(record.severity) +
      "</div>" +
      '<div class="drawer-kv"><span>Alert ID</span><strong class="mono">' +
      escapeHtml(record.alert_id || "--") +
      "</strong></div>" +
      '<div class="drawer-kv"><span>Retry Count</span><strong class="mono">' +
      escapeHtml(String(record.retry_count != null ? record.retry_count : 0)) +
      "</strong></div>" +
      '<div class="drawer-kv"><span>Created (UTC)</span><span class="mono" style="color:var(--fg);">' +
      escapeHtml(record.created_at || "--") +
      "</span></div>" +
      '<div class="drawer-kv"><span>Delivered (UTC)</span><span class="mono" style="color:var(--fg);">' +
      escapeHtml(record.delivered_at || "--") +
      "</span></div>" +
      "</div>" +
      '<div class="drawer-kv"><span>Target Channels</span>' +
      renderChannelChipsHtml(record.target_channels) +
      "</div>" +
      '<div class="drawer-kv"><span>Message</span><div style="font-size:0.84rem;color:var(--fg);">' +
      escapeHtml(record.message || "(no message)") +
      "</div></div>" +
      errorNotice +
      '<div><span class="field-label" style="display:block;margin-bottom:6px;">Raw NotificationLog JSON</span>' +
      '<pre class="response-pre mono" style="padding:10px;border-radius:8px;border:1px solid var(--border);background:var(--code-bg);">' +
      escapeHtml(JSON.stringify(record, null, 2)) +
      "</pre></div>";
  }

  async function openDetailDrawer(notificationId) {
    var drawer = $("detail-drawer");
    var bodyEl = $("detail-drawer-body");
    if (!drawer || !notificationId) return;

    state.drawer.lastFocusEl = doc.activeElement;
    state.drawer.notificationId = notificationId;
    state.drawer.open = true;
    drawer.hidden = false;

    if (bodyEl) {
      bodyEl.innerHTML = '<div class="empty-inspector">Loading notification ' + escapeHtml(notificationId) + "...</div>";
    }
    var closeBtn = $("btn-close-drawer");
    if (closeBtn) closeBtn.focus();

    var res = await apiFetch("/notifications/" + encodeURIComponent(notificationId));
    if (res.ok && res.data) {
      state.drawer.currentRecord = res.data;
      renderDrawerBody(res.data);
    } else if (bodyEl) {
      renderResponseInspector(bodyEl, res, "Failed to load notification");
    }
  }

  function closeDetailDrawer() {
    var drawer = $("detail-drawer");
    if (!drawer || drawer.hidden) return;
    drawer.hidden = true;
    state.drawer.open = false;
    state.drawer.notificationId = null;
    if (state.drawer.lastFocusEl && typeof state.drawer.lastFocusEl.focus === "function") {
      state.drawer.lastFocusEl.focus();
    }
    state.drawer.lastFocusEl = null;
  }

  async function performManualRetry(notificationId, openDrawerAfter) {
    if (!notificationId) return null;
    var res = await apiFetch("/notifications/" + encodeURIComponent(notificationId) + "/retry", {
      method: "POST"
    });
    if (res.ok && res.data) {
      var st = res.data.status || "updated";
      showToast(
        "Manual Retry Executed",
        (res.data.alert_id || shortId(notificationId)) + " -> " + st + " (retry_count=" + res.data.retry_count + ")",
        st === "delivered" ? "success" : "warning"
      );
      if (state.drawer.open && state.drawer.notificationId === notificationId) {
        state.drawer.currentRecord = res.data;
        renderDrawerBody(res.data);
      } else if (openDrawerAfter) {
        renderDrawerBody(res.data);
      }
      await refreshAll();
      return res;
    }

    var detail = res.data && res.data.detail ? res.data.detail : "HTTP " + res.status;
    showToast("Retry Rejected (" + res.status + ")", detail, "error");
    return res;
  }

  function initDrawerAndRowClicks() {
    var drawer = $("detail-drawer");
    var closeBtn = $("btn-close-drawer");
    var drawerRetryBtn = $("btn-drawer-retry");

    if (closeBtn) {
      closeBtn.addEventListener("click", closeDetailDrawer);
    }
    if (drawer) {
      drawer.addEventListener("click", function (ev) {
        if (ev.target && ev.target.getAttribute("data-drawer-close") === "true") {
          closeDetailDrawer();
        }
      });
    }
    doc.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && state.drawer.open) {
        ev.preventDefault();
        closeDetailDrawer();
      }
    });
    if (drawerRetryBtn) {
      drawerRetryBtn.addEventListener("click", function () {
        if (state.drawer.notificationId) {
          performManualRetry(state.drawer.notificationId, false);
        }
      });
    }

    var overviewBody = $("overview-recent-body");
    if (overviewBody) {
      overviewBody.addEventListener("click", function (ev) {
        var btn = ev.target && ev.target.closest ? ev.target.closest("[data-open-detail]") : null;
        if (btn) {
          openDetailDrawer(btn.getAttribute("data-open-detail"));
          return;
        }
        var row = ev.target && ev.target.closest ? ev.target.closest("tr[data-nid]") : null;
        if (row) {
          openDetailDrawer(row.getAttribute("data-nid"));
        }
      });
    }
  }

  // ------------------------------------------------------------------ Tab 2: Simulator & Composer
  function findLatestAlertContext(alertId) {
    if (!alertId) return null;
    var lists = [state.recentNotifications, state.explorer.items];
    for (var i = 0; i < lists.length; i += 1) {
      var arr = lists[i];
      if (!Array.isArray(arr)) continue;
      for (var j = 0; j < arr.length; j += 1) {
        if (arr[j] && arr[j].alert_id === alertId) {
          return arr[j];
        }
      }
    }
    return null;
  }

  function getComposerSelectedChannels() {
    var boxes = doc.querySelectorAll('#event-composer-form input[name="target_channels"]:checked');
    var channels = [];
    for (var i = 0; i < boxes.length; i += 1) {
      channels.push(boxes[i].value);
    }
    return channels;
  }

  function buildPayloadFromComposerForm() {
    var eventName = ($("composer-event-name") && $("composer-event-name").value) || "alert.created";
    var alertId = ($("composer-alert-id") && $("composer-alert-id").value.trim()) || "ALT-101";
    var eventId = ($("composer-event-id") && $("composer-event-id").value.trim()) || DS.generateUuidV4();
    var corrId = ($("composer-correlation-id") && $("composer-correlation-id").value.trim()) || "corr-demo-101";
    var severity = $("composer-severity") ? $("composer-severity").value : "high";
    var levelVal = $("composer-escalation-level") ? $("composer-escalation-level").value : "2";
    var timestamp = ($("composer-timestamp") && $("composer-timestamp").value.trim()) || DS.isoUtc();
    var message = $("composer-message") ? $("composer-message").value : "";
    var resolutionNote = $("composer-resolution-note") ? $("composer-resolution-note").value : "";
    var customChannels = getComposerSelectedChannels();

    return DS.buildEventPayload(eventName, {
      event_id: eventId,
      alert_id: alertId,
      correlationId: corrId,
      severity: severity || undefined,
      escalation_level: levelVal ? Number(levelVal) : 2,
      message: message,
      resolution_note: resolutionNote,
      target_channels: customChannels.length > 0 ? customChannels : undefined,
      timestamp: timestamp
    });
  }

  function updateComposerFieldVisibility() {
    var eventName = ($("composer-event-name") && $("composer-event-name").value) || "alert.created";
    var sevWrap = doc.querySelector('[data-composer-field="severity"]');
    var escWrap = doc.querySelector('[data-composer-field="escalation_level"]');
    var msgWrap = doc.querySelector('[data-composer-field="message"]');
    var resWrap = doc.querySelector('[data-composer-field="resolution_note"]');
    var sevSelect = $("composer-severity");
    var inheritOpt = sevSelect ? sevSelect.querySelector('option[value=""]') : null;

    if (eventName === "alert.created") {
      if (sevWrap) sevWrap.hidden = false;
      if (escWrap) escWrap.hidden = true;
      if (msgWrap) msgWrap.hidden = false;
      if (resWrap) resWrap.hidden = true;
      if (inheritOpt) inheritOpt.disabled = true;
      if (sevSelect && !sevSelect.value) sevSelect.value = "high";
    } else if (eventName === "alert.escalated") {
      if (sevWrap) sevWrap.hidden = false;
      if (escWrap) escWrap.hidden = false;
      if (msgWrap) msgWrap.hidden = false;
      if (resWrap) resWrap.hidden = true;
      if (inheritOpt) inheritOpt.disabled = false;
    } else {
      if (sevWrap) sevWrap.hidden = true;
      if (escWrap) escWrap.hidden = true;
      if (msgWrap) msgWrap.hidden = true;
      if (resWrap) resWrap.hidden = false;
    }
  }

  function updateComposerRoutingPreview(overridePayload) {
    var previewEl = $("composer-routing-preview");
    if (!previewEl || !DS) return;

    var payload = overridePayload;
    var eventName = payload && payload.event_name
      ? payload.event_name
      : (($("composer-event-name") && $("composer-event-name").value) || "alert.created");
    var alertId = payload && payload.alert_id
      ? payload.alert_id
      : ($("composer-alert-id") && $("composer-alert-id").value.trim());
    var severity = payload
      ? (payload.severity || "")
      : ($("composer-severity") ? $("composer-severity").value : "high");
    var escLevel = payload && payload.escalation_level !== undefined
      ? payload.escalation_level
      : ($("composer-escalation-level") ? Number($("composer-escalation-level").value) : 2);
    var customChannels = payload
      ? (Array.isArray(payload.target_channels) ? payload.target_channels : [])
      : getComposerSelectedChannels();

    var ctx = findLatestAlertContext(alertId);
    var info = DS.explainRouting(eventName, severity, escLevel, customChannels, ctx);

    previewEl.innerHTML =
      renderChannelChipsHtml(info.channels) +
      '<span style="font-size:0.75rem;color:var(--muted);margin-left:4px;">' +
      escapeHtml(info.summary) +
      "</span>";
  }

  function syncRawTextareaFromForm() {
    var rawArea = $("composer-raw-json");
    if (!rawArea) return;
    var payload = buildPayloadFromComposerForm();
    rawArea.value = JSON.stringify(payload, null, 2);
    updateComposerRoutingPreview(payload);
  }

  function syncFormFromRawTextarea() {
    var rawArea = $("composer-raw-json");
    if (!rawArea) return;
    var parsed;
    try {
      parsed = JSON.parse(rawArea.value);
    } catch (_) {
      return;
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return;

    if (parsed.event_name && DS.VALID_EVENTS.indexOf(parsed.event_name) !== -1 && $("composer-event-name")) {
      $("composer-event-name").value = parsed.event_name;
      updateComposerFieldVisibility();
    }
    if (typeof parsed.alert_id === "string" && $("composer-alert-id")) {
      $("composer-alert-id").value = parsed.alert_id;
    }
    if (typeof parsed.event_id === "string" && $("composer-event-id")) {
      $("composer-event-id").value = parsed.event_id;
    }
    if (typeof parsed.correlationId === "string" && $("composer-correlation-id")) {
      $("composer-correlation-id").value = parsed.correlationId;
    }
    if ($("composer-severity") && (typeof parsed.severity === "string" || parsed.severity === undefined)) {
      var sevVal = parsed.severity || "";
      if ($("composer-event-name") && $("composer-event-name").value === "alert.created" && !sevVal) {
        sevVal = "high";
      }
      $("composer-severity").value = sevVal;
    }
    if (parsed.escalation_level !== undefined && $("composer-escalation-level")) {
      $("composer-escalation-level").value = String(parsed.escalation_level);
    }
    if ($("composer-message")) {
      $("composer-message").value = typeof parsed.message === "string" ? parsed.message : "";
    }
    if ($("composer-resolution-note")) {
      $("composer-resolution-note").value = typeof parsed.resolution_note === "string" ? parsed.resolution_note : "";
    }
    if (typeof parsed.timestamp === "string" && $("composer-timestamp")) {
      $("composer-timestamp").value = parsed.timestamp;
    }
    var chList = Array.isArray(parsed.target_channels) ? parsed.target_channels : [];
    var boxes = doc.querySelectorAll('#event-composer-form input[name="target_channels"]');
    for (var i = 0; i < boxes.length; i += 1) {
      boxes[i].checked = chList.indexOf(boxes[i].value) !== -1;
    }
    updateComposerRoutingPreview(parsed);
  }

  function clearComposerValidationErrors() {
    var summary = $("composer-error-summary");
    if (summary) {
      summary.hidden = true;
      summary.innerHTML = "";
    }
    var form = $("event-composer-form");
    if (!form) return;

    var invalidEls = form.querySelectorAll('[aria-invalid="true"]');
    for (var i = 0; i < invalidEls.length; i += 1) {
      invalidEls[i].removeAttribute("aria-invalid");
      invalidEls[i].removeAttribute("aria-describedby");
    }
    var inlineErrors = form.querySelectorAll(".field-inline-error");
    for (var j = 0; j < inlineErrors.length; j += 1) {
      if (inlineErrors[j].parentNode) {
        inlineErrors[j].parentNode.removeChild(inlineErrors[j]);
      }
    }
  }

  function renderComposerValidationErrors(errors) {
    var summary = $("composer-error-summary");
    if (!summary || !Array.isArray(errors) || errors.length === 0) return;

    errors.forEach(function (err) {
      var fieldEl = $(err.fieldId);
      if (!fieldEl) return;
      var errSpanId = "err-" + err.fieldId;
      fieldEl.setAttribute("aria-invalid", "true");
      fieldEl.setAttribute("aria-describedby", errSpanId);

      var span = doc.createElement("span");
      span.id = errSpanId;
      span.className = "field-inline-error";
      span.textContent = err.message;
      if (fieldEl.parentNode) {
        fieldEl.parentNode.appendChild(span);
      }
    });

    summary.innerHTML = "";
    var title = doc.createElement("strong");
    title.textContent = "Please fix " + errors.length + " validation issue(s) before dispatching:";
    var ul = doc.createElement("ul");

    errors.forEach(function (err) {
      var li = doc.createElement("li");
      var link = doc.createElement("a");
      link.href = "#" + err.fieldId;
      link.textContent = err.label + ": " + err.message;
      link.addEventListener("click", function (ev) {
        ev.preventDefault();
        var target = $(err.fieldId);
        if (target && typeof target.focus === "function") {
          target.focus();
        }
      });
      li.appendChild(link);
      ul.appendChild(li);
    });

    summary.appendChild(title);
    summary.appendChild(ul);
    summary.hidden = false;
    summary.focus();
  }

  function validateComposerSubmission(rawMode) {
    var errors = [];
    var rawArea = $("composer-raw-json");
    var payload = null;

    if (rawMode && rawArea) {
      try {
        payload = JSON.parse(rawArea.value);
      } catch (e) {
        errors.push({
          fieldId: "composer-raw-json",
          label: "Raw JSON",
          message: "Invalid JSON syntax (" + (e && e.message ? e.message : "parse error") + ")."
        });
        return { valid: false, errors: errors, payload: null };
      }
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        errors.push({
          fieldId: "composer-raw-json",
          label: "Raw JSON",
          message: "Payload must be a JSON object."
        });
        return { valid: false, errors: errors, payload: null };
      }

      if (DS.VALID_EVENTS.indexOf(payload.event_name) === -1) {
        errors.push({
          fieldId: "composer-raw-json",
          label: "event_name",
          message: "event_name must be alert.created, alert.escalated, or alert.resolved."
        });
      }
      if (!payload.event_id || !UUID_RE.test(String(payload.event_id))) {
        errors.push({
          fieldId: "composer-raw-json",
          label: "event_id",
          message: "event_id must be a valid UUIDv4 string."
        });
      }
      if (payload.source !== "core-business") {
        errors.push({
          fieldId: "composer-raw-json",
          label: "source",
          message: 'source must equal "core-business".'
        });
      }
      if (!payload.alert_id || !ALERT_ID_RE.test(String(payload.alert_id))) {
        errors.push({
          fieldId: "composer-raw-json",
          label: "alert_id",
          message: "alert_id must match ^ALT-[0-9]{3,}$ (e.g. ALT-101)."
        });
      }
      if (!payload.correlationId || String(payload.correlationId).trim().length < 1 || String(payload.correlationId).length > 100) {
        errors.push({
          fieldId: "composer-raw-json",
          label: "correlationId",
          message: "correlationId must be 1..100 characters."
        });
      }
      if (!payload.timestamp || !ISO_TZ_RE.test(String(payload.timestamp)) || Number.isNaN(Date.parse(payload.timestamp))) {
        errors.push({
          fieldId: "composer-raw-json",
          label: "timestamp",
          message: "timestamp must be ISO 8601 date-time with timezone (e.g. 2026-11-23T04:30:00Z)."
        });
      }
      if (payload.event_name === "alert.created") {
        if (!DS.SEVERITY_ROUTING[payload.severity]) {
          errors.push({
            fieldId: "composer-raw-json",
            label: "severity",
            message: "severity must be low, medium, high, or critical."
          });
        }
        if (typeof payload.message !== "string" || payload.message.trim().length < 5 || payload.message.length > 500) {
          errors.push({
            fieldId: "composer-raw-json",
            label: "message",
            message: "message is required (5..500 characters)."
          });
        }
      } else if (payload.event_name === "alert.escalated") {
        var lvl = Number(payload.escalation_level);
        if (!Number.isInteger(lvl) || lvl < 1 || lvl > 5) {
          errors.push({
            fieldId: "composer-raw-json",
            label: "escalation_level",
            message: "escalation_level must be an integer between 1 and 5."
          });
        }
      } else if (payload.event_name === "alert.resolved") {
        if (typeof payload.resolution_note !== "string" || payload.resolution_note.trim().length < 3 || payload.resolution_note.length > 500) {
          errors.push({
            fieldId: "composer-raw-json",
            label: "resolution_note",
            message: "resolution_note is required (3..500 characters)."
          });
        }
      }
      if (payload.target_channels !== undefined && payload.target_channels !== null) {
        if (!Array.isArray(payload.target_channels) || payload.target_channels.length < 1 || payload.target_channels.length > 4) {
          errors.push({
            fieldId: "composer-raw-json",
            label: "target_channels",
            message: "target_channels must be an array of 1..4 valid channels."
          });
        } else {
          var seen = Object.create(null);
          for (var c = 0; c < payload.target_channels.length; c += 1) {
            var ch = payload.target_channels[c];
            if (DS.VALID_CHANNELS.indexOf(ch) === -1 || seen[ch]) {
              errors.push({
                fieldId: "composer-raw-json",
                label: "target_channels",
                message: "target_channels must contain unique values from telegram, email, discord, sms."
              });
              break;
            }
            seen[ch] = true;
          }
        }
      }

      return { valid: errors.length === 0, errors: errors, payload: payload };
    }

    var eventName = ($("composer-event-name") && $("composer-event-name").value) || "alert.created";
    var alertId = ($("composer-alert-id") && $("composer-alert-id").value.trim()) || "";
    var eventId = ($("composer-event-id") && $("composer-event-id").value.trim()) || "";
    var corrId = ($("composer-correlation-id") && $("composer-correlation-id").value.trim()) || "";
    var severity = $("composer-severity") ? $("composer-severity").value : "";
    var escLevelRaw = $("composer-escalation-level") ? $("composer-escalation-level").value.trim() : "";
    var timestamp = ($("composer-timestamp") && $("composer-timestamp").value.trim()) || "";
    var message = $("composer-message") ? $("composer-message").value.trim() : "";
    var resolutionNote = $("composer-resolution-note") ? $("composer-resolution-note").value.trim() : "";

    if (!ALERT_ID_RE.test(alertId)) {
      errors.push({
        fieldId: "composer-alert-id",
        label: "alert_id",
        message: "Must match ^ALT-[0-9]{3,}$ (for example ALT-101)."
      });
    }
    if (eventId && !UUID_RE.test(eventId)) {
      errors.push({
        fieldId: "composer-event-id",
        label: "event_id",
        message: "Leave blank to auto-generate or enter a valid UUIDv4."
      });
    }
    if (!corrId || corrId.length > 100) {
      errors.push({
        fieldId: "composer-correlation-id",
        label: "correlationId",
        message: "Required (1 to 100 characters)."
      });
    }
    if (!timestamp || !ISO_TZ_RE.test(timestamp) || Number.isNaN(Date.parse(timestamp))) {
      errors.push({
        fieldId: "composer-timestamp",
        label: "timestamp",
        message: "Must be RFC 3339 UTC/offset timestamp (e.g. 2026-11-23T04:30:00Z)."
      });
    }

    if (eventName === "alert.created") {
      if (!DS.SEVERITY_ROUTING[severity]) {
        errors.push({
          fieldId: "composer-severity",
          label: "severity",
          message: "Select low, medium, high, or critical."
        });
      }
      if (message.length < 5 || message.length > 500) {
        errors.push({
          fieldId: "composer-message",
          label: "message",
          message: "Must be between 5 and 500 characters."
        });
      }
    } else if (eventName === "alert.escalated") {
      var escNum = Number(escLevelRaw);
      if (!escLevelRaw || !Number.isInteger(escNum) || escNum < 1 || escNum > 5) {
        errors.push({
          fieldId: "composer-escalation-level",
          label: "escalation_level",
          message: "Must be an integer from 1 to 5."
        });
      }
      if (message.length > 0 && (message.length < 5 || message.length > 500)) {
        errors.push({
          fieldId: "composer-message",
          label: "message",
          message: "Optional message must be 5 to 500 characters when provided."
        });
      }
    } else if (eventName === "alert.resolved") {
      if (resolutionNote.length < 3 || resolutionNote.length > 500) {
        errors.push({
          fieldId: "composer-resolution-note",
          label: "resolution_note",
          message: "Must be between 3 and 500 characters."
        });
      }
    }

    if (errors.length > 0) {
      return { valid: false, errors: errors, payload: null };
    }

    if (!eventId && $("composer-event-id")) {
      eventId = DS.generateUuidV4();
      $("composer-event-id").value = eventId;
    }

    payload = buildPayloadFromComposerForm();
    return { valid: true, errors: [], payload: payload };
  }

  async function runScenario(scenarioId) {
    var meta = (DS.SCENARIO_METADATA && DS.SCENARIO_METADATA[scenarioId]) || {
      title: scenarioId,
      stages: ["core", "validator", "store", "delivery"]
    };
    var respBox = $("composer-response");
    var pipeEl = $("pipeline-visualizer");

    if (respBox) {
      respBox.innerHTML = '<div class="empty-inspector">Running scenario ' + escapeHtml(meta.title) + "...</div>";
    }

    var mqttMap = {
      "mqtt-lifecycle": { scenario: "lifecycle", alert_id: "ALT-601" },
      "mqtt-q05": { scenario: "duplicate_q05", alert_id: "ALT-605" },
      "mqtt-q09": { scenario: "out_of_order_q09", alert_id: "ALT-690" },
      "mqtt-q08-dlq": { scenario: "invalid_schema_dlq", alert_id: "ALT-608" }
    };

    if (mqttMap[scenarioId]) {
      var mRes = await apiFetch("/demo-api/mqtt/publish", {
        method: "POST",
        body: mqttMap[scenarioId]
      });
      renderResponseInspector(respBox, mRes, meta.title);
      if (pipeEl && DC) {
        DC.pulsePipeline(
          pipeEl,
          meta.stages,
          !mRes.ok ? "error" : scenarioId === "mqtt-q08-dlq" ? "failed" : scenarioId === "mqtt-q09" ? "duplicate_ignored" : "ok"
        );
      }
      if (mRes.ok) {
        showToast("MQTT Scenario Published", meta.title, "success");
        await new Promise(function (resolve) { global.setTimeout(resolve, 400); });
        await refreshAll();
        if (scenarioId === "mqtt-q08-dlq") {
          await refreshFaultsAndDlq();
        }
      } else {
        showToast("MQTT Publish Unavailable", (mRes.data && mRes.data.detail) || "HTTP " + mRes.status, "warning");
      }
      return;
    }

    if (scenarioId === "rest-lifecycle") {
      var alertId = "ALT-" + String(Math.floor(620 + Math.random() * 70));
      var corrId = "req-rest-life-" + DS.generateUuidV4().slice(0, 8);
      var events = [
        DS.buildEventPayload("alert.created", {
          alert_id: alertId,
          correlationId: corrId,
          severity: "high",
          message: "[REST Lifecycle] Initial high alert on " + alertId,
          offsetSeconds: -10
        }),
        DS.buildEventPayload("alert.escalated", {
          alert_id: alertId,
          correlationId: corrId,
          escalation_level: 3,
          severity: "critical",
          message: "[REST Lifecycle] Escalated " + alertId + " to level 3",
          offsetSeconds: -5
        }),
        DS.buildEventPayload("alert.resolved", {
          alert_id: alertId,
          correlationId: corrId,
          resolution_note: "REST Lifecycle verification completed.",
          target_channels: ["email", "discord"],
          offsetSeconds: 0
        })
      ];

      var stepResults = [];
      var totalMs = 0;
      var allOk = true;
      for (var s = 0; s < events.length; s += 1) {
        var stepRes = await apiFetch("/notifications", { method: "POST", body: events[s] });
        totalMs += stepRes.ms;
        if (!stepRes.ok) allOk = false;
        stepResults.push({
          step: s + 1,
          event_name: events[s].event_name,
          status: stepRes.status,
          ms: stepRes.ms,
          response: stepRes.data
        });
      }

      renderResponseInspector(
        respBox,
        {
          status: allOk ? 201 : stepResults[stepResults.length - 1].status,
          statusText: allOk ? "Lifecycle Complete (3x 201)" : "Partial Error",
          ms: totalMs,
          headers: { "content-type": "application/json" },
          data: { alert_id: alertId, correlationId: corrId, steps: stepResults }
        },
        meta.title
      );
      if (pipeEl && DC) DC.pulsePipeline(pipeEl, meta.stages, allOk ? "ok" : "error");
      showToast("REST Lifecycle Complete", alertId + " (created -> escalated -> resolved)", allOk ? "success" : "warning");
      await refreshAll();
      return;
    }

    if (scenarioId === "rest-q05") {
      var preset409 = DS.buildRestErrorPreset(409);
      var first = await apiFetch(preset409.path, { method: preset409.method, body: preset409.body });
      var second = await apiFetch(preset409.path, { method: preset409.method, body: preset409.body });

      renderResponseInspector(
        respBox,
        {
          status: second.status,
          statusText: "1st=" + first.status + " · 2nd=" + second.status,
          ms: first.ms + second.ms,
          headers: second.headers,
          data: {
            event_id: preset409.body.event_id,
            first_attempt: { status: first.status, ms: first.ms, data: first.data },
            second_attempt_duplicate: { status: second.status, ms: second.ms, problem: second.data }
          }
        },
        meta.title
      );
      if (pipeEl && DC) DC.pulsePipeline(pipeEl, meta.stages, second.status === 409 ? "duplicate_ignored" : "ok");
      showToast("Q05 Idempotency Tested", "1st: " + first.status + ", 2nd duplicate: " + second.status, "info");
      await refreshAll();
      return;
    }

    if (scenarioId === "err-401" || scenarioId === "err-422" || scenarioId === "err-400") {
      var code = scenarioId.replace("err-", "");
      var preset = DS.buildRestErrorPreset(code);
      var errRes = await apiFetch(preset.path, {
        method: preset.method,
        authMode: preset.authMode === "invalid" ? "override" : "default",
        overrideToken: preset.overrideToken,
        body: preset.body
      });
      renderResponseInspector(respBox, errRes, preset.title);
      if (pipeEl && DC) DC.pulsePipeline(pipeEl, meta.stages, String(errRes.status));
      showToast("RFC 9457 Error Captured", "HTTP " + errRes.status + " (" + preset.slug + ")", "warning");
    }
  }

  function initSimulator() {
    var scenarioBtns = doc.querySelectorAll("[data-scenario]");
    for (var i = 0; i < scenarioBtns.length; i += 1) {
      (function (btn) {
        btn.addEventListener("click", function () {
          runScenario(btn.getAttribute("data-scenario"));
        });
      })(scenarioBtns[i]);
    }

    var form = $("event-composer-form");
    var eventSelect = $("composer-event-name");
    var rawToggle = $("composer-raw-toggle");
    var rawJson = $("composer-raw-json");
    var fillUuidBtn = $("btn-composer-fill-uuid");

    if ($("composer-event-id") && !$("composer-event-id").value) {
      $("composer-event-id").value = DS.generateUuidV4();
    }
    if ($("composer-timestamp") && !$("composer-timestamp").value) {
      $("composer-timestamp").value = DS.isoUtc();
    }
    updateComposerFieldVisibility();
    syncRawTextareaFromForm();

    if (eventSelect) {
      eventSelect.addEventListener("change", function () {
        updateComposerFieldVisibility();
        syncRawTextareaFromForm();
      });
    }

    if (fillUuidBtn) {
      fillUuidBtn.addEventListener("click", function () {
        if ($("composer-event-id")) $("composer-event-id").value = DS.generateUuidV4();
        if ($("composer-correlation-id")) $("composer-correlation-id").value = "corr-demo-" + DS.generateUuidV4().slice(0, 8);
        if ($("composer-timestamp")) $("composer-timestamp").value = DS.isoUtc();
        syncRawTextareaFromForm();
      });
    }

    if (rawToggle && rawJson) {
      rawToggle.addEventListener("change", function () {
        rawJson.readOnly = !rawToggle.checked;
        if (!rawToggle.checked) {
          syncFormFromRawTextarea();
          syncRawTextareaFromForm();
        }
      });
      rawJson.addEventListener("input", function () {
        if (rawToggle.checked) {
          syncFormFromRawTextarea();
        }
      });
    }

    if (form) {
      form.addEventListener("input", function (ev) {
        if (ev.target && ev.target.id === "composer-raw-json") return;
        syncRawTextareaFromForm();
      });
      form.addEventListener("change", function (ev) {
        if (ev.target && (ev.target.id === "composer-raw-json" || ev.target.id === "composer-raw-toggle")) return;
        syncRawTextareaFromForm();
      });

      form.addEventListener("submit", async function (ev) {
        ev.preventDefault();
        clearComposerValidationErrors();

        var isRawMode = Boolean(rawToggle && rawToggle.checked);
        var check = validateComposerSubmission(isRawMode);
        if (!check.valid) {
          renderComposerValidationErrors(check.errors);
          return;
        }

        var transportRadio = form.querySelector('input[name="transport"]:checked');
        var transport = transportRadio ? transportRadio.value : "mqtt";
        var respBox = $("composer-response");
        var pipeEl = $("pipeline-visualizer");

        var res;
        if (transport === "mqtt") {
          res = await apiFetch("/demo-api/mqtt/publish", {
            method: "POST",
            body: { payload: check.payload }
          });
          renderResponseInspector(respBox, res, "MQTT Publish -> " + check.payload.event_name);
          if (pipeEl && DC) {
            DC.pulsePipeline(pipeEl, ["core", "mqtt", "validator", "store", "delivery"], res.ok ? "ok" : "error");
          }
          if (res.ok) {
            showToast("MQTT Event Dispatched", check.payload.alert_id + " · " + check.payload.event_name, "success");
            await new Promise(function (resolve) { global.setTimeout(resolve, 350); });
            await refreshAll();
          } else {
            showToast("MQTT Dispatch Failed", (res.data && res.data.detail) || "HTTP " + res.status, "error");
          }
        } else {
          res = await apiFetch("/notifications", {
            method: "POST",
            body: check.payload
          });
          renderResponseInspector(respBox, res, "REST POST /notifications");
          if (pipeEl && DC) {
            var st = res.ok && res.data ? res.data.status : "error";
            DC.pulsePipeline(
              pipeEl,
              st === "failed" ? ["core", "validator", "store", "delivery", "dlq"] : ["core", "validator", "store", "delivery"],
              st
            );
          }
          if (res.ok) {
            showToast("REST Notification Sent", check.payload.alert_id + " -> " + ((res.data && res.data.status) || "201"), "success");
            await refreshAll();
          } else {
            showToast("REST Error (" + res.status + ")", (res.data && res.data.detail) || "Validation failed", "error");
          }
        }
      });
    }
  }

  // ------------------------------------------------------------------ Tab 3: Log Explorer
  function renderExplorerTable(items) {
    var tbody = $("explorer-table-body");
    var countLabel = $("explorer-count-label");
    var cursorLabel = $("cursor-indicator");
    var prevBtn = $("btn-page-prev");
    var nextBtn = $("btn-page-next");

    if (countLabel) {
      countLabel.textContent = (items ? items.length : 0) + " items shown";
    }
    if (cursorLabel) {
      var pageNum = state.explorer.cursorStack.length + 1;
      cursorLabel.textContent =
        "Page " + pageNum + (state.explorer.currentCursor ? " · cursor=" + state.explorer.currentCursor : "");
    }
    if (prevBtn) {
      prevBtn.disabled = state.explorer.cursorStack.length === 0;
    }
    if (nextBtn) {
      nextBtn.disabled = !state.explorer.hasMore || !state.explorer.nextCursor;
    }

    if (!tbody) return;
    if (!Array.isArray(items) || items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="table-empty">No notification records match these filters.</td></tr>';
      return;
    }

    tbody.innerHTML = items
      .map(function (item) {
        var nid = item.notification_id || "";
        var retryBlocked = ["retrying", "queued", "duplicate_ignored"].indexOf(item.status) !== -1;
        return (
          '<tr data-nid="' +
          escapeHtml(nid) +
          '">' +
          '<td class="mono">' +
          escapeHtml(formatUtcTime(item.created_at)) +
          "</td>" +
          '<td class="mono" title="' +
          escapeHtml(nid) +
          '">' +
          escapeHtml(shortId(nid)) +
          "</td>" +
          '<td class="mono"><strong>' +
          escapeHtml(item.alert_id || "--") +
          "</strong></td>" +
          "<td><code>" +
          escapeHtml(item.event_name || "--") +
          "</code></td>" +
          "<td>" +
          renderSeverityBadgeHtml(item.severity) +
          "</td>" +
          "<td>" +
          renderChannelChipsHtml(item.target_channels) +
          "</td>" +
          "<td>" +
          renderStatusBadgeHtml(item.status) +
          "</td>" +
          '<td class="mono">' +
          escapeHtml(String(item.retry_count != null ? item.retry_count : 0)) +
          "</td>" +
          '<td><div style="display:flex;gap:6px;flex-wrap:wrap;">' +
          '<button type="button" class="btn btn-ghost btn-sm" data-exp-view="' +
          escapeHtml(nid) +
          '">View</button>' +
          '<button type="button" class="btn btn-ghost btn-sm" data-exp-retry="' +
          escapeHtml(nid) +
          '"' +
          (retryBlocked ? " disabled" : "") +
          ">Retry</button>" +
          "</div></td>" +
          "</tr>"
        );
      })
      .join("");
  }

  async function refreshExplorer() {
    if (!state.token) {
      renderExplorerTable([]);
      return;
    }
    var params = new URLSearchParams();
    params.set("limit", String(state.explorer.filters.limit || 20));
    if (state.explorer.filters.alert_id) params.set("alert_id", state.explorer.filters.alert_id);
    if (state.explorer.filters.status) params.set("status", state.explorer.filters.status);
    if (state.explorer.filters.channel) params.set("channel", state.explorer.filters.channel);
    if (state.explorer.currentCursor) params.set("cursor", state.explorer.currentCursor);

    var res = await apiFetch("/notifications?" + params.toString());
    if (res.ok && res.data) {
      state.explorer.items = Array.isArray(res.data.items) ? res.data.items : [];
      state.explorer.nextCursor = res.data.next_cursor || null;
      state.explorer.hasMore = Boolean(res.data.has_more);
      renderExplorerTable(state.explorer.items);
    } else if (res.status === 400 || res.status === 422) {
      showToast("Invalid Filter", (res.data && res.data.detail) || "Check filter format (e.g. ALT-101)", "warning");
    }
  }

  function initExplorer() {
    var applyBtn = $("btn-filter-apply");
    var resetBtn = $("btn-filter-reset");
    var prevBtn = $("btn-page-prev");
    var nextBtn = $("btn-page-next");
    var alertInput = $("filter-alert-id");
    var statusSelect = $("filter-status");
    var channelSelect = $("filter-channel");
    var limitSelect = $("filter-limit");
    var tbody = $("explorer-table-body");

    function readFiltersAndFetch() {
      state.explorer.filters.alert_id = alertInput ? alertInput.value.trim() : "";
      state.explorer.filters.status = statusSelect ? statusSelect.value : "";
      state.explorer.filters.channel = channelSelect ? channelSelect.value : "";
      state.explorer.filters.limit = limitSelect ? parseInt(limitSelect.value, 10) || 20 : 20;
      state.explorer.cursorStack = [];
      state.explorer.currentCursor = null;
      refreshExplorer();
    }

    if (applyBtn) applyBtn.addEventListener("click", readFiltersAndFetch);
    if (statusSelect) statusSelect.addEventListener("change", readFiltersAndFetch);
    if (channelSelect) channelSelect.addEventListener("change", readFiltersAndFetch);
    if (limitSelect) limitSelect.addEventListener("change", readFiltersAndFetch);
    if (alertInput) {
      alertInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          readFiltersAndFetch();
        }
      });
    }
    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        if (alertInput) alertInput.value = "";
        if (statusSelect) statusSelect.value = "";
        if (channelSelect) channelSelect.value = "";
        if (limitSelect) limitSelect.value = "20";
        readFiltersAndFetch();
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        if (!state.explorer.hasMore || !state.explorer.nextCursor) return;
        state.explorer.cursorStack.push(state.explorer.currentCursor);
        state.explorer.currentCursor = state.explorer.nextCursor;
        refreshExplorer();
      });
    }
    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        if (state.explorer.cursorStack.length === 0) return;
        state.explorer.currentCursor = state.explorer.cursorStack.pop() || null;
        refreshExplorer();
      });
    }

    if (tbody) {
      tbody.addEventListener("click", function (ev) {
        var viewBtn = ev.target && ev.target.closest ? ev.target.closest("[data-exp-view]") : null;
        if (viewBtn) {
          openDetailDrawer(viewBtn.getAttribute("data-exp-view"));
          return;
        }
        var retryBtn = ev.target && ev.target.closest ? ev.target.closest("[data-exp-retry]") : null;
        if (retryBtn) {
          performManualRetry(retryBtn.getAttribute("data-exp-retry"), false);
        }
      });
    }
  }

  // ------------------------------------------------------------------ Tab 4: Faults & DLQ
  function renderDlqList(items) {
    var listEl = $("dlq-list");
    var badgeEl = $("dlq-count-badge");
    if (badgeEl) badgeEl.textContent = String(Array.isArray(items) ? items.length : 0);
    if (!listEl) return;

    if (!Array.isArray(items) || items.length === 0) {
      listEl.innerHTML = '<div class="empty-inspector">No DLQ records captured in this session yet.</div>';
      return;
    }

    listEl.innerHTML = items
      .map(function (item, idx) {
        var nid = item.notification_id || "";
        var highlightStyle = idx === state.highlightedDlqIndex
          ? ' style="box-shadow:0 0 0 2px var(--warning), var(--shadow-card);"'
          : "";
        var orig = item.original_payload ? String(item.original_payload).slice(0, 260) : "";

        return (
          '<article class="dlq-item-card"' +
          highlightStyle +
          ">" +
          '<div class="dlq-item-head">' +
          '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">' +
          '<span class="badge badge-danger">' +
          escapeHtml(item.reason || "DLQ_ERROR") +
          "</span>" +
          (item.alert_id ? '<strong class="mono">' + escapeHtml(item.alert_id) + "</strong>" : "") +
          '<span class="badge badge-neutral mono">retries=' +
          escapeHtml(String(item.retry_count != null ? item.retry_count : 0)) +
          "</span>" +
          '<span class="sync-label mono">' +
          escapeHtml(formatUtcTime(item.failed_at)) +
          "</span>" +
          "</div>" +
          '<div style="display:flex;gap:6px;flex-wrap:wrap;">' +
          (nid
            ? '<button type="button" class="btn btn-ghost btn-sm" data-dlq-view="' +
              escapeHtml(nid) +
              '">Inspect</button>' +
              '<button type="button" class="btn btn-primary btn-sm" data-dlq-retry="' +
              escapeHtml(nid) +
              '">Quick Retry</button>'
            : "") +
          "</div>" +
          "</div>" +
          '<div style="font-size:0.82rem;">' +
          escapeHtml(item.error_detail || "No error detail") +
          "</div>" +
          (orig
            ? '<pre class="response-pre mono" style="font-size:0.74rem;opacity:0.9;">' + escapeHtml(orig) + "</pre>"
            : "") +
          "</article>"
        );
      })
      .join("");
  }

  async function refreshFaultsAndDlq() {
    if (!state.token) return;
    var results = await Promise.all([
      apiFetch("/demo-api/faults"),
      apiFetch("/demo-api/dlq")
    ]);
    var fRes = results[0];
    var dRes = results[1];

    if (fRes.ok && fRes.data) {
      updateFaultIndicators(fRes.data);
    }
    if (dRes.ok && dRes.data && Array.isArray(dRes.data.items)) {
      state.dlqItems = dRes.data.items;
      for (var i = 0; i < dRes.data.items.length; i += 1) {
        if (dRes.data.items[i].notification_id) {
          state.lastFailedNotificationId = dRes.data.items[i].notification_id;
          break;
        }
      }
      renderDlqList(dRes.data.items);
    }
  }

  async function applyFaultControls() {
    var channels = [];
    var boxes = doc.querySelectorAll("[data-fault-channel]:checked");
    for (var i = 0; i < boxes.length; i += 1) {
      channels.push(boxes[i].getAttribute("data-fault-channel"));
    }

    var maxRetriesRaw = $("fault-max-retries") ? $("fault-max-retries").value.trim() : "";
    var intervalRaw = $("fault-retry-interval") ? $("fault-retry-interval").value.trim() : "";

    var body = {
      fail_channels: channels,
      max_retries: maxRetriesRaw === "" ? null : Number(maxRetriesRaw),
      retry_interval_seconds: intervalRaw === "" ? null : Number(intervalRaw)
    };

    var res = await apiFetch("/demo-api/faults", { method: "POST", body: body });
    if (res.ok && res.data) {
      updateFaultIndicators(res.data);
      showToast("Fault Overrides Applied", "fail_channels=[" + channels.join(", ") + "]", "warning");
      await refreshOverviewAndRecent();
    } else {
      showToast("Invalid Fault Settings", (res.data && res.data.detail) || "HTTP " + res.status, "error");
    }
  }

  async function resetFaultControls() {
    var res = await apiFetch("/demo-api/faults/reset", { method: "POST" });
    if (res.ok && res.data) {
      updateFaultIndicators(res.data);
      showToast("Faults Cleared", "Restored service environment defaults.", "success");
      await refreshOverviewAndRecent();
    }
    return res;
  }

  async function runGuidedFaultStep(step) {
    if (step === "1") {
      var fRes = await apiFetch("/demo-api/faults", {
        method: "POST",
        body: { fail_channels: ["sms"], max_retries: 0 }
      });
      if (!fRes.ok) {
        showToast("Step 1 Failed", (fRes.data && fRes.data.detail) || "Could not set fault overrides", "error");
        return;
      }
      updateFaultIndicators(fRes.data);

      var alertId = "ALT-" + String(Math.floor(800 + Math.random() * 190));
      var payload = DS.buildEventPayload("alert.created", {
        alert_id: alertId,
        severity: "critical",
        target_channels: ["sms"],
        message: "[Guided Fault Demo] Critical SMS dispatch expected to hit DLQ"
      });

      var sentViaMqtt = false;
      if (state.config && state.config.mqtt_enabled && state.mqttConnected) {
        var mqRes = await apiFetch("/demo-api/mqtt/publish", {
          method: "POST",
          body: { payload: payload }
        });
        if (mqRes.ok) {
          sentViaMqtt = true;
          for (var attempt = 0; attempt < 6; attempt += 1) {
            await new Promise(function (resolve) { global.setTimeout(resolve, 250); });
            var checkDlq = await apiFetch("/demo-api/dlq", { recordLatency: false });
            if (
              checkDlq.ok &&
              checkDlq.data &&
              Array.isArray(checkDlq.data.items) &&
              checkDlq.data.items.some(function (it) { return it.alert_id === alertId; })
            ) {
              break;
            }
          }
        }
      }

      if (!sentViaMqtt) {
        var rRes = await apiFetch("/notifications", { method: "POST", body: payload });
        if (rRes.ok && rRes.data && rRes.data.notification_id) {
          state.lastFailedNotificationId = rRes.data.notification_id;
        }
      }

      await refreshFaultsAndDlq();
      await refreshOverviewAndRecent();
      showToast("Step 1 Complete", "SMS fault injected + " + alertId + " sent to DLQ.", "warning");
      return;
    }

    if (step === "2") {
      state.highlightedDlqIndex = 0;
      await refreshFaultsAndDlq();
      if (state.dlqItems.length > 0) {
        var dlqEl = $("dlq-list");
        if (dlqEl && dlqEl.firstElementChild && typeof dlqEl.firstElementChild.scrollIntoView === "function") {
          dlqEl.firstElementChild.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
        showToast("Step 2 Complete", "Inspected " + state.dlqItems.length + " DLQ item(s).", "info");
      } else {
        showToast("DLQ Empty", "Run Step 1 first to generate a MAX_RETRIES_EXCEEDED DLQ record.", "warning");
      }
      return;
    }

    if (step === "3") {
      await resetFaultControls();
      state.highlightedDlqIndex = -1;

      var targetId = state.lastFailedNotificationId;
      if (!targetId) {
        for (var i = 0; i < state.dlqItems.length; i += 1) {
          if (state.dlqItems[i].notification_id) {
            targetId = state.dlqItems[i].notification_id;
            break;
          }
        }
      }
      if (!targetId) {
        var failedLookup = await apiFetch("/notifications?status=failed&limit=1");
        if (failedLookup.ok && failedLookup.data && Array.isArray(failedLookup.data.items) && failedLookup.data.items.length > 0) {
          targetId = failedLookup.data.items[0].notification_id;
        }
      }

      if (!targetId) {
        showToast("No Failed Record Found", "Run Step 1 first to produce a failed notification.", "warning");
        return;
      }

      var retryRes = await performManualRetry(targetId, false);
      if (retryRes && retryRes.ok && retryRes.data && retryRes.data.status === "delivered") {
        await refreshFaultsAndDlq();
        showToast("Step 3 Complete", "Faults reset and notification recovered -> delivered!", "success");
      }
    }
  }

  function initFaults() {
    var applyBtn = $("btn-apply-faults");
    var resetBtn = $("btn-reset-faults");
    var refreshDlqBtn = $("btn-refresh-dlq");
    var dlqList = $("dlq-list");

    if (applyBtn) applyBtn.addEventListener("click", applyFaultControls);
    if (resetBtn) resetBtn.addEventListener("click", resetFaultControls);
    if (refreshDlqBtn) refreshDlqBtn.addEventListener("click", refreshFaultsAndDlq);

    var stepBtns = doc.querySelectorAll("[data-fault-step]");
    for (var i = 0; i < stepBtns.length; i += 1) {
      (function (btn) {
        btn.addEventListener("click", function () {
          runGuidedFaultStep(btn.getAttribute("data-fault-step"));
        });
      })(stepBtns[i]);
    }

    if (dlqList) {
      dlqList.addEventListener("click", function (ev) {
        var viewBtn = ev.target && ev.target.closest ? ev.target.closest("[data-dlq-view]") : null;
        if (viewBtn) {
          openDetailDrawer(viewBtn.getAttribute("data-dlq-view"));
          return;
        }
        var retryBtn = ev.target && ev.target.closest ? ev.target.closest("[data-dlq-retry]") : null;
        if (retryBtn) {
          performManualRetry(retryBtn.getAttribute("data-dlq-retry"), false).then(refreshFaultsAndDlq);
        }
      });
    }
  }

  // ------------------------------------------------------------------ Tab 5: Delivery Feed & 7 REST APIs
  function renderDeliveryFeed() {
    var listEl = $("delivery-feed-list");
    if (!listEl) return;

    var filter = state.feedFilterChannel || "all";
    var items = state.deliveryFeed.filter(function (entry) {
      return filter === "all" || entry.channel === filter;
    });

    if (items.length === 0) {
      listEl.innerHTML =
        '<div class="empty-inspector">No channel deliveries recorded' +
        (filter !== "all" ? " for " + escapeHtml(filter) : "") +
        " yet.</div>";
      return;
    }

    listEl.innerHTML = items
      .map(function (entry) {
        var ch = String(entry.channel || "telegram").toLowerCase();
        var chInfo = (DS.CHANNELS && DS.CHANNELS[ch]) || { label: ch, recipientHint: "recipient" };
        var ok = entry.ok !== false;
        var modeLabel = entry.mode === "webhook" ? "Real Webhook" : "Stdout Mock";

        return (
          '<article class="feed-card feed-card-' +
          escapeHtml(ch) +
          '">' +
          '<div class="feed-card-head">' +
          '<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">' +
          '<span class="channel-chip ch-' +
          escapeHtml(ch) +
          '">' +
          escapeHtml(chInfo.label) +
          "</span>" +
          '<span class="badge ' +
          (entry.mode === "webhook" ? "badge-info" : "badge-neutral") +
          '">' +
          escapeHtml(modeLabel) +
          "</span>" +
          "</div>" +
          '<span class="badge ' +
          (ok ? "badge-success" : "badge-danger") +
          '">' +
          (ok ? "Delivered" : "Failed") +
          "</span>" +
          "</div>" +
          '<div class="feed-card-meta mono">' +
          "<span>To: " +
          escapeHtml(chInfo.recipientHint) +
          "</span>" +
          "<span>Alert: " +
          escapeHtml(entry.alert_id || "--") +
          "</span>" +
          "</div>" +
          '<p class="feed-card-body">' +
          escapeHtml(entry.message || "") +
          "</p>" +
          (entry.error
            ? '<div style="font-size:0.76rem;color:var(--danger-text);font-weight:600;">' +
              escapeHtml(entry.error) +
              "</div>"
            : "") +
          '<div class="feed-card-meta mono">' +
          "<span>" +
          escapeHtml(formatUtcTime(entry.timestamp)) +
          "</span>" +
          "<span>" +
          escapeHtml(String(entry.duration_ms != null ? entry.duration_ms : 0)) +
          " ms</span>" +
          "<span>" +
          escapeHtml(entry.correlationId || "--") +
          "</span>" +
          "</div>" +
          "</article>"
        );
      })
      .join("");
  }

  async function refreshDeliveryFeed() {
    if (!state.token) {
      renderDeliveryFeed();
      return;
    }
    var res = await apiFetch("/demo-api/delivery-feed");
    if (res.ok && res.data && Array.isArray(res.data.items)) {
      state.deliveryFeed = res.data.items;
      renderDeliveryFeed();
    }
  }

  function getApiInputState(endpoint) {
    if (!state.apiTester.inputsById[endpoint.id]) {
      var defaultJson = "";
      if (endpoint.defaultBody) {
        var cloned = JSON.parse(JSON.stringify(endpoint.defaultBody));
        cloned.event_id = DS.generateUuidV4();
        cloned.timestamp = DS.isoUtc();
        defaultJson = JSON.stringify(cloned, null, 2);
      }
      state.apiTester.inputsById[endpoint.id] = {
        notification_id: state.latestNotificationId || "",
        limit: endpoint.defaultParams && endpoint.defaultParams.limit ? String(endpoint.defaultParams.limit) : "",
        alert_id: "",
        status: "",
        channel: "",
        cursor: "",
        bodyText: defaultJson
      };
    } else if (
      endpoint.pathParams.indexOf("notification_id") !== -1 &&
      !state.apiTester.inputsById[endpoint.id].notification_id &&
      state.latestNotificationId
    ) {
      state.apiTester.inputsById[endpoint.id].notification_id = state.latestNotificationId;
    }
    return state.apiTester.inputsById[endpoint.id];
  }

  function renderApiTesterGrid() {
    var grid = $("api-tester-grid");
    if (!grid || !DS || !Array.isArray(DS.REST_API_CATALOG)) return;

    grid.innerHTML = DS.REST_API_CATALOG.map(function (ep) {
      var selected = state.apiTester.selectedId === ep.id;
      var inputs = getApiInputState(ep);

      var editorHtml = "";
      if (selected) {
        var fields = "";
        if (ep.pathParams.indexOf("notification_id") !== -1) {
          fields +=
            '<div class="field-group">' +
            '<label class="field-label" for="api-param-nid-' +
            escapeHtml(ep.id) +
            '">Path: notification_id (UUID)</label>' +
            '<div style="display:flex;gap:6px;">' +
            '<input id="api-param-nid-' +
            escapeHtml(ep.id) +
            '" data-api-field="notification_id" class="input input-sm mono" value="' +
            escapeHtml(inputs.notification_id) +
            '" placeholder="Paste notification_id UUID...">' +
            '<button type="button" class="btn btn-ghost btn-sm" data-api-fill-latest="' +
            escapeHtml(ep.id) +
            '">Latest ID</button>' +
            "</div></div>";
        }
        if (ep.queryParams.length > 0) {
          fields += '<div class="form-grid-2">';
          ep.queryParams.forEach(function (qp) {
            fields +=
              '<div class="field-group">' +
              '<label class="field-label" for="api-qp-' +
              escapeHtml(ep.id + "-" + qp) +
              '">Query: ' +
              escapeHtml(qp) +
              "</label>" +
              '<input id="api-qp-' +
              escapeHtml(ep.id + "-" + qp) +
              '" data-api-field="' +
              escapeHtml(qp) +
              '" class="input input-sm mono" value="' +
              escapeHtml(inputs[qp] || "") +
              '" placeholder="optional">' +
              "</div>";
          });
          fields += "</div>";
        }
        if (ep.method === "POST" && ep.defaultBody) {
          fields +=
            '<div class="field-group">' +
            '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">' +
            '<label class="field-label" for="api-body-' +
            escapeHtml(ep.id) +
            '">JSON Request Body</label>' +
            '<button type="button" class="btn btn-ghost btn-sm" data-api-fresh-uuid="' +
            escapeHtml(ep.id) +
            '">Fresh UUID &amp; Time</button>' +
            "</div>" +
            '<textarea id="api-body-' +
            escapeHtml(ep.id) +
            '" data-api-field="bodyText" class="input mono json-textarea" rows="7" spellcheck="false">' +
            escapeHtml(inputs.bodyText) +
            "</textarea></div>";
        }

        editorHtml =
          '<div style="padding-top:6px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:8px;">' +
          '<p class="card-subtitle" style="margin:0;">' +
          escapeHtml(ep.description) +
          "</p>" +
          fields +
          '<div class="form-actions">' +
          '<button type="button" class="btn btn-primary btn-sm" data-api-exec="' +
          escapeHtml(ep.id) +
          '">Execute ' +
          escapeHtml(ep.method + " " + ep.pathTemplate) +
          "</button>" +
          "</div>" +
          "</div>";
      }

      return (
        '<article class="api-endpoint-card' +
        (selected ? " is-selected" : "") +
        '" data-api-card="' +
        escapeHtml(ep.id) +
        '">' +
        '<div class="api-endpoint-head">' +
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">' +
        '<span class="method-badge method-' +
        escapeHtml(ep.method) +
        '">' +
        escapeHtml(ep.method) +
        "</span>" +
        '<code class="mono">' +
        escapeHtml(ep.pathTemplate) +
        "</code>" +
        '<span class="badge ' +
        (ep.authRequired ? "badge-warning" : "badge-success") +
        '">' +
        (ep.authRequired ? "Bearer Auth" : "Public") +
        "</span>" +
        "</div>" +
        '<button type="button" class="btn btn-ghost btn-sm" data-api-select="' +
        escapeHtml(ep.id) +
        '">' +
        (selected ? "Selected" : "Inspect / Run") +
        "</button>" +
        "</div>" +
        '<div style="font-size:0.8rem;color:var(--muted);">' +
        escapeHtml(ep.summary) +
        "</div>" +
        editorHtml +
        "</article>"
      );
    }).join("");
  }

  async function executeApiTesterEndpoint(endpointId) {
    var ep = DS.REST_API_CATALOG.find(function (item) {
      return item.id === endpointId;
    });
    if (!ep) return;

    var inputs = getApiInputState(ep);
    var path = ep.pathTemplate;

    if (ep.pathParams.indexOf("notification_id") !== -1) {
      var nid = (inputs.notification_id || "").trim() || state.latestNotificationId || "00000000-0000-0000-0000-000000000000";
      path = path.replace("{notification_id}", encodeURIComponent(nid));
    }

    if (ep.queryParams.length > 0) {
      var qs = new URLSearchParams();
      ep.queryParams.forEach(function (qp) {
        var val = (inputs[qp] || "").trim();
        if (val !== "") qs.set(qp, val);
      });
      var qStr = qs.toString();
      if (qStr) path += "?" + qStr;
    }

    var opts = {
      method: ep.method,
      authMode: ep.authRequired ? "default" : "none"
    };

    if (ep.method === "POST" && ep.defaultBody) {
      opts.rawBody = inputs.bodyText;
    }

    var outEl = $("api-tester-output");
    if (outEl) {
      outEl.innerHTML = '<div class="empty-inspector">Executing ' + escapeHtml(ep.method + " " + path) + "...</div>";
    }

    var res = await apiFetch(path, opts);
    renderResponseInspector(outEl, res, ep.method + " " + path);
    if (res.ok && ep.method === "POST") {
      await refreshAll();
    }
  }

  function initChannelsAndApiTester() {
    var refreshFeedBtn = $("btn-refresh-feed");
    if (refreshFeedBtn) {
      refreshFeedBtn.addEventListener("click", refreshDeliveryFeed);
    }

    var filterChips = doc.querySelectorAll("[data-feed-channel]");
    for (var i = 0; i < filterChips.length; i += 1) {
      (function (chip) {
        chip.addEventListener("click", function () {
          state.feedFilterChannel = chip.getAttribute("data-feed-channel") || "all";
          for (var j = 0; j < filterChips.length; j += 1) {
            var active = filterChips[j] === chip;
            filterChips[j].classList.toggle("is-active", active);
            filterChips[j].setAttribute("aria-pressed", active ? "true" : "false");
          }
          renderDeliveryFeed();
        });
      })(filterChips[i]);
    }

    var testerGrid = $("api-tester-grid");
    if (testerGrid) {
      testerGrid.addEventListener("input", function (ev) {
        var target = ev.target;
        if (!target || !target.getAttribute) return;
        var field = target.getAttribute("data-api-field");
        if (!field) return;
        var ep = DS.REST_API_CATALOG.find(function (item) {
          return item.id === state.apiTester.selectedId;
        });
        if (!ep) return;
        getApiInputState(ep)[field] = target.value;
      });

      testerGrid.addEventListener("click", function (ev) {
        var selectBtn = ev.target && ev.target.closest ? ev.target.closest("[data-api-select]") : null;
        if (selectBtn) {
          state.apiTester.selectedId = selectBtn.getAttribute("data-api-select");
          renderApiTesterGrid();
          return;
        }
        var fillBtn = ev.target && ev.target.closest ? ev.target.closest("[data-api-fill-latest]") : null;
        if (fillBtn) {
          var eid = fillBtn.getAttribute("data-api-fill-latest");
          var ep = DS.REST_API_CATALOG.find(function (item) { return item.id === eid; });
          if (ep) {
            getApiInputState(ep).notification_id = state.latestNotificationId || "";
            renderApiTesterGrid();
          }
          return;
        }
        var uuidBtn = ev.target && ev.target.closest ? ev.target.closest("[data-api-fresh-uuid]") : null;
        if (uuidBtn) {
          var epId = uuidBtn.getAttribute("data-api-fresh-uuid");
          var epObj = DS.REST_API_CATALOG.find(function (item) { return item.id === epId; });
          if (epObj) {
            var inp = getApiInputState(epObj);
            var parsed = null;
            try {
              parsed = JSON.parse(inp.bodyText);
            } catch (_) {
              parsed = JSON.parse(JSON.stringify(epObj.defaultBody));
            }
            if (parsed && typeof parsed === "object") {
              parsed.event_id = DS.generateUuidV4();
              parsed.timestamp = DS.isoUtc();
              inp.bodyText = JSON.stringify(parsed, null, 2);
              renderApiTesterGrid();
            }
          }
          return;
        }
        var execBtn = ev.target && ev.target.closest ? ev.target.closest("[data-api-exec]") : null;
        if (execBtn) {
          executeApiTesterEndpoint(execBtn.getAttribute("data-api-exec"));
        }
      });
    }

    renderApiTesterGrid();
  }

  // ------------------------------------------------------------------ Bootstrap
  async function bootstrap() {
    initTheme();
    initTabs();
    initAuthControls();
    initDrawerAndRowClicks();
    initSimulator();
    initExplorer();
    initFaults();
    initChannelsAndApiTester();

    await loadConfigAndAuth();
    await refreshAll();
    initPolling();
  }

  if (doc.readyState === "loading") {
    doc.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})(window, document);
