/**
 * Smart Campus Notification Service — Scenarios, Contract Metadata & Routing Helpers
 * Exports `window.DemoScenarios` for app.js and interactive UI components.
 */
(function (global) {
  "use strict";

  var SEVERITY_ROUTING = Object.freeze({
    low: ["email"],
    medium: ["telegram", "email"],
    high: ["telegram", "email", "discord"],
    critical: ["telegram", "email", "discord", "sms"]
  });

  var VALID_CHANNELS = ["telegram", "email", "discord", "sms"];
  var VALID_EVENTS = ["alert.created", "alert.escalated", "alert.resolved"];

  var CHANNELS = Object.freeze({
    telegram: {
      id: "telegram",
      label: "Telegram",
      shortLabel: "TG",
      modeHint: "Bot API sendMessage (if token & chat_id configured) or deterministic stdout mock",
      recipientHint: "Campus Operations On-Call Group"
    },
    email: {
      id: "email",
      label: "Email",
      shortLabel: "Mail",
      modeHint: "SMTP digest relay or deterministic stdout mock",
      recipientHint: "ops-alerts@campus.local"
    },
    discord: {
      id: "discord",
      label: "Discord",
      shortLabel: "Discord",
      modeHint: "Discord Webhook POST (if DISCORD_WEBHOOK_URL set) or stdout mock",
      recipientHint: "#campus-security-alerts"
    },
    sms: {
      id: "sms",
      label: "SMS",
      shortLabel: "SMS",
      modeHint: "Emergency SMS gateway or deterministic stdout mock",
      recipientHint: "+84-90-CAMPUS-SEC"
    }
  });

  var STATUS_META = Object.freeze({
    delivered: {
      id: "delivered",
      label: "Delivered",
      className: "status-delivered",
      tone: "success",
      iconKey: "check",
      description: "Dispatched to all target channels"
    },
    retrying: {
      id: "retrying",
      label: "Retrying",
      className: "status-retrying",
      tone: "warning",
      iconKey: "refresh",
      description: "Awaiting automatic retry interval"
    },
    failed: {
      id: "failed",
      label: "Failed",
      className: "status-failed",
      tone: "danger",
      iconKey: "alert",
      description: "Delivery failed and routed to DLQ"
    },
    duplicate_ignored: {
      id: "duplicate_ignored",
      label: "Suppressed",
      className: "status-suppressed",
      tone: "info",
      iconKey: "shield",
      description: "Out-of-order (Q09) or duplicate event suppressed"
    },
    queued: {
      id: "queued",
      label: "Queued",
      className: "status-queued",
      tone: "neutral",
      iconKey: "clock",
      description: "Accepted and queued for delivery"
    }
  });

  function generateUuidV4() {
    if (global.crypto && typeof global.crypto.randomUUID === "function") {
      return global.crypto.randomUUID();
    }
    var bytes = new Uint8Array(16);
    if (global.crypto && typeof global.crypto.getRandomValues === "function") {
      global.crypto.getRandomValues(bytes);
    } else {
      for (var i = 0; i < 16; i += 1) {
        bytes[i] = Math.floor(Math.random() * 256);
      }
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    var hex = Array.prototype.map.call(bytes, function (b) {
      return b.toString(16).padStart(2, "0");
    });
    return (
      hex.slice(0, 4).join("") +
      "-" +
      hex.slice(4, 6).join("") +
      "-" +
      hex.slice(6, 8).join("") +
      "-" +
      hex.slice(8, 10).join("") +
      "-" +
      hex.slice(10, 16).join("")
    );
  }

  function isoUtc(offsetSeconds) {
    var ms = Date.now() + (typeof offsetSeconds === "number" ? offsetSeconds * 1000 : 0);
    var d = new Date(ms);
    return d.toISOString().replace(/\.\d{3}Z$/, "Z");
  }

  function shortHex(len) {
    return generateUuidV4().replace(/-/g, "").slice(0, len || 8);
  }

  function sanitizeChannels(customChannels) {
    if (!Array.isArray(customChannels)) {
      return [];
    }
    var seen = Object.create(null);
    var result = [];
    for (var i = 0; i < customChannels.length; i += 1) {
      var ch = String(customChannels[i] || "").trim().toLowerCase();
      if (VALID_CHANNELS.indexOf(ch) !== -1 && !seen[ch]) {
        seen[ch] = true;
        result.push(ch);
      }
    }
    return result;
  }

  /**
   * Mirrors backend NotificationStore._derive() logic so the composer displays
   * the exact target_channels that will be dispatched.
   */
  function predictChannels(eventName, severity, escalationLevel, customChannels, previousContext) {
    var custom = sanitizeChannels(customChannels);
    if (custom.length > 0) {
      return custom;
    }

    var ev = eventName || "alert.created";
    if (ev === "alert.created") {
      var sev = SEVERITY_ROUTING[severity] ? severity : "high";
      return SEVERITY_ROUTING[sev].slice();
    }

    if (ev === "alert.escalated") {
      var effSev;
      if (severity && SEVERITY_ROUTING[severity]) {
        effSev = severity;
      } else {
        var base = previousContext && previousContext.severity && SEVERITY_ROUTING[previousContext.severity]
          ? previousContext.severity
          : "high";
        var level = Number(escalationLevel) || 2;
        effSev = level >= 3 ? "critical" : base;
      }
      return SEVERITY_ROUTING[effSev].slice();
    }

    if (ev === "alert.resolved") {
      if (previousContext && Array.isArray(previousContext.target_channels) && previousContext.target_channels.length > 0) {
        var inherited = sanitizeChannels(previousContext.target_channels);
        if (inherited.length > 0) {
          return inherited;
        }
      }
      return ["telegram"];
    }

    return SEVERITY_ROUTING.high.slice();
  }

  function explainRouting(eventName, severity, escalationLevel, customChannels, previousContext) {
    var custom = sanitizeChannels(customChannels);
    var channels = predictChannels(eventName, severity, escalationLevel, customChannels, previousContext);
    if (custom.length > 0) {
      return {
        channels: channels,
        mode: "custom",
        effectiveSeverity: severity || null,
        summary: "Explicit target_channels override selected by producer (" + channels.join(", ") + ")."
      };
    }
    var ev = eventName || "alert.created";
    if (ev === "alert.created") {
      var sev = SEVERITY_ROUTING[severity] ? severity : "high";
      return {
        channels: channels,
        mode: "severity",
        effectiveSeverity: sev,
        summary: "Auto-routed by severity \"" + sev + "\" -> " + channels.join(", ") + "."
      };
    }
    if (ev === "alert.escalated") {
      var level = Number(escalationLevel) || 2;
      var effSev = severity && SEVERITY_ROUTING[severity]
        ? severity
        : level >= 3
          ? "critical"
          : ((previousContext && previousContext.severity) || "high");
      return {
        channels: channels,
        mode: "escalation",
        effectiveSeverity: effSev,
        summary: "Escalation level " + level + " resolves severity \"" + effSev + "\" -> " + channels.join(", ") + "."
      };
    }
    var hasPrev = previousContext && Array.isArray(previousContext.target_channels) && previousContext.target_channels.length > 0;
    return {
      channels: channels,
      mode: hasPrev ? "inherited" : "fallback",
      effectiveSeverity: (previousContext && previousContext.severity) || null,
      summary: hasPrev
        ? "Inherits latest alert channels for " + (previousContext.alert_id || "alert") + " -> " + channels.join(", ") + "."
        : "No prior alert record in local context; backend uses prior DB channels or fallback [telegram]."
    };
  }

  function buildEventPayload(eventName, opts) {
    var options = opts || {};
    var ev = VALID_EVENTS.indexOf(eventName) !== -1 ? eventName : "alert.created";
    var alertId = options.alert_id && String(options.alert_id).trim() ? String(options.alert_id).trim() : "ALT-601";
    var payload = {
      event_id: options.event_id || generateUuidV4(),
      event_name: ev,
      correlationId:
        options.correlationId && String(options.correlationId).trim()
          ? String(options.correlationId).trim()
          : "req-demo-" + shortHex(8),
      source: options.source || "core-business",
      alert_id: alertId
    };

    var channels = sanitizeChannels(options.target_channels);

    if (ev === "alert.created") {
      payload.severity = SEVERITY_ROUTING[options.severity] ? options.severity : "high";
      payload.message =
        options.message && String(options.message).trim()
          ? String(options.message).trim()
          : "[Demo] Security anomaly detected on " + alertId + " at Gate B1";
      if (channels.length > 0) {
        payload.target_channels = channels;
      }
    } else if (ev === "alert.escalated") {
      var rawLevel = options.escalation_level !== undefined ? Number(options.escalation_level) : 3;
      payload.escalation_level = Number.isFinite(rawLevel) ? Math.min(5, Math.max(1, Math.round(rawLevel))) : 3;
      if (options.severity && SEVERITY_ROUTING[options.severity]) {
        payload.severity = options.severity;
      }
      if (options.message && String(options.message).trim()) {
        payload.message = String(options.message).trim();
      }
      if (channels.length > 0) {
        payload.target_channels = channels;
      }
    } else if (ev === "alert.resolved") {
      payload.resolution_note =
        options.resolution_note && String(options.resolution_note).trim()
          ? String(options.resolution_note).trim()
          : "Campus security team verified and resolved the incident.";
      if (channels.length > 0) {
        payload.target_channels = channels;
      }
    }

    payload.timestamp =
      options.timestamp && String(options.timestamp).trim()
        ? String(options.timestamp).trim()
        : isoUtc(options.offsetSeconds);

    return payload;
  }

  function buildRestErrorPreset(code) {
    var key = String(code);
    if (key === "401") {
      return {
        code: 401,
        slug: "err-401",
        title: "401 Unauthorized (RFC 9457)",
        description: "Sends POST /notifications with an invalid Bearer token to trigger WWW-Authenticate + ProblemDetails.",
        method: "POST",
        path: "/notifications",
        authMode: "invalid",
        overrideToken: "invalid-demo-token",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/problem+json"
        },
        body: buildEventPayload("alert.created", {
          alert_id: "ALT-401",
          severity: "low",
          message: "Unauthorized request demonstration payload"
        })
      };
    }

    if (key === "422") {
      var badBody = buildEventPayload("alert.created", {
        alert_id: "ALT-422",
        severity: "high",
        message: "Invalid channel enum test (zalo is unsupported per contract Q03)"
      });
      badBody.target_channels = ["telegram", "zalo"];
      return {
        code: 422,
        slug: "err-422",
        title: "422 Unprocessable Entity (Q03 Schema Violation)",
        description: "Valid JSON containing unsupported channel \"zalo\" to trigger ENUM_MISMATCH ProblemDetails.",
        method: "POST",
        path: "/notifications",
        authMode: "current",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/problem+json"
        },
        body: badBody
      };
    }

    if (key === "400") {
      return {
        code: 400,
        slug: "err-400",
        title: "400 Bad Request (Query Limit > 100)",
        description: "Queries GET /notifications?limit=101 (exceeds OpenAPI maximum 100) to trigger RFC 9457 validation error.",
        method: "GET",
        path: "/notifications?limit=101",
        authMode: "current",
        headers: {
          Accept: "application/problem+json"
        },
        body: null,
        malformedAlternative: {
          method: "POST",
          path: "/notifications",
          rawBody: '{"event_name": "alert.created", "broken_json": '
        }
      };
    }

    if (key === "409") {
      return {
        code: 409,
        slug: "err-409",
        title: "409 Conflict (Q05 Idempotency Duplicate)",
        description: "Sends the exact same event_id twice via POST /notifications: 1st returns 201 Created, 2nd returns 409 Conflict.",
        method: "POST",
        path: "/notifications",
        authMode: "current",
        repeatCount: 2,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/problem+json"
        },
        body: buildEventPayload("alert.created", {
          alert_id: "ALT-605",
          severity: "medium",
          message: "Q05 REST duplicate idempotency check payload"
        })
      };
    }

    return buildRestErrorPreset("422");
  }

  var REST_API_CATALOG = [
    {
      id: "getHealth",
      method: "GET",
      path: "/health",
      pathTemplate: "/health",
      authRequired: false,
      tag: "health",
      summary: "Liveness & DB ping",
      description: "Public healthcheck verifying database connectivity and MQTT configuration (200 ok or 503 service-unavailable).",
      pathParams: [],
      queryParams: [],
      defaultParams: {},
      defaultBody: null
    },
    {
      id: "getReadiness",
      method: "GET",
      path: "/ready",
      pathTemplate: "/ready",
      authRequired: false,
      tag: "health",
      summary: "Dependency readiness (DB + MQTT)",
      description: "Readiness probe checking PostgreSQL/memory backend and live MQTT broker connection (200 ready or 503 degraded).",
      pathParams: [],
      queryParams: [],
      defaultParams: {},
      defaultBody: null
    },
    {
      id: "sendNotification",
      method: "POST",
      path: "/notifications",
      pathTemplate: "/notifications",
      authRequired: true,
      tag: "notifications",
      summary: "Send notification event (REST sync fallback)",
      description: "Submit alert.created, alert.escalated, or alert.resolved synchronously via REST with UUIDv4 event_id idempotency.",
      pathParams: [],
      queryParams: [],
      defaultParams: {},
      defaultBody: {
        event_id: "00000000-0000-4000-8000-000000000001",
        event_name: "alert.created",
        correlationId: "req-openapi-tester-01",
        source: "core-business",
        alert_id: "ALT-701",
        severity: "high",
        message: "OpenAPI REST Sync Fallback test event from Control Center",
        timestamp: "2026-11-23T10:00:00Z"
      }
    },
    {
      id: "listNotifications",
      method: "GET",
      path: "/notifications",
      pathTemplate: "/notifications",
      authRequired: true,
      tag: "notifications",
      summary: "List notification logs (filter + cursor)",
      description: "Paginated notification history filtered by optional alert_id, status, channel, cursor, and limit (1..100).",
      pathParams: [],
      queryParams: ["limit", "alert_id", "status", "channel", "cursor"],
      defaultParams: { limit: 10 },
      defaultBody: null
    },
    {
      id: "getRecentNotifications",
      method: "GET",
      path: "/notifications/recent",
      pathTemplate: "/notifications/recent",
      authRequired: true,
      tag: "notifications",
      summary: "Recent notifications feed",
      description: "Fast cursor-paginated feed of the newest notification logs for monitoring dashboards and Analytics.",
      pathParams: [],
      queryParams: ["limit", "cursor"],
      defaultParams: { limit: 6 },
      defaultBody: null
    },
    {
      id: "getNotificationById",
      method: "GET",
      path: "/notifications/{notification_id}",
      pathTemplate: "/notifications/{notification_id}",
      authRequired: true,
      tag: "notifications",
      summary: "Get notification detail by ID",
      description: "Retrieve a single NotificationLog record including delivery status, retry_count, and error_detail.",
      pathParams: ["notification_id"],
      queryParams: [],
      defaultParams: { notification_id: "" },
      defaultBody: null
    },
    {
      id: "retryNotification",
      method: "POST",
      path: "/notifications/{notification_id}/retry",
      pathTemplate: "/notifications/{notification_id}/retry",
      authRequired: true,
      tag: "notifications",
      summary: "Manual retry notification",
      description: "Manually retry a failed notification (or eligible record). Returns 409 if retrying, queued, suppressed, or limit reached.",
      pathParams: ["notification_id"],
      queryParams: [],
      defaultParams: { notification_id: "" },
      defaultBody: null
    }
  ];

  var SCENARIO_METADATA = Object.freeze({
    "mqtt-lifecycle": {
      id: "mqtt-lifecycle",
      transport: "mqtt",
      title: "MQTT Full Lifecycle (ALT-601)",
      description: "Publishes alert.created (high) -> alert.escalated (level 3) -> alert.resolved onto campus.alerts.",
      stages: ["core", "mqtt", "validator", "store", "delivery"]
    },
    "rest-lifecycle": {
      id: "rest-lifecycle",
      transport: "rest",
      title: "REST Full Lifecycle (ALT-602)",
      description: "Sequentially POSTs alert.created -> alert.escalated -> alert.resolved via /notifications.",
      stages: ["core", "validator", "store", "delivery"]
    },
    "mqtt-q05": {
      id: "mqtt-q05",
      transport: "mqtt",
      title: "MQTT Q05 Duplicate Dedupe",
      description: "Publishes identical event_id twice over MQTT; consumer logs once and skips duplicate.",
      stages: ["core", "mqtt", "validator", "store", "delivery"]
    },
    "rest-q05": {
      id: "rest-q05",
      transport: "rest",
      title: "REST Q05 Duplicate -> 409",
      description: "POSTs identical event_id twice to /notifications; 1st returns 201 Created, 2nd returns 409 Conflict.",
      stages: ["core", "validator", "store"]
    },
    "mqtt-q09": {
      id: "mqtt-q09",
      transport: "mqtt",
      title: "MQTT Q09 Out-of-Order Suppression",
      description: "Publishes alert.resolved (now) before delayed alert.created (now - 5m) -> SUPPRESSED_OUT_OF_ORDER.",
      stages: ["core", "mqtt", "validator", "store"]
    },
    "mqtt-q08-dlq": {
      id: "mqtt-q08-dlq",
      transport: "mqtt",
      title: "MQTT Q08 Invalid Schema -> DLQ",
      description: "Publishes unsupported alert.deleted / EXTREME severity -> rejected straight to campus.alerts.dlq.",
      stages: ["core", "mqtt", "validator", "dlq"]
    },
    "err-401": {
      id: "err-401",
      transport: "rest",
      title: "RFC 9457: 401 Unauthorized",
      description: "Sends request with invalid Bearer token to inspect WWW-Authenticate and ProblemDetails.",
      stages: ["core", "validator"]
    },
    "err-422": {
      id: "err-422",
      transport: "rest",
      title: "RFC 9457: 422 Unprocessable (zalo)",
      description: "Submits unsupported channel \"zalo\" to inspect field-level ENUM_MISMATCH ProblemDetails.",
      stages: ["core", "validator"]
    },
    "err-400": {
      id: "err-400",
      transport: "rest",
      title: "RFC 9457: 400 Bad Request",
      description: "Queries /notifications?limit=101 to inspect query validation ProblemDetails.",
      stages: ["core", "validator"]
    }
  });

  global.DemoScenarios = Object.freeze({
    SEVERITY_ROUTING: SEVERITY_ROUTING,
    CHANNELS: CHANNELS,
    VALID_CHANNELS: VALID_CHANNELS,
    VALID_EVENTS: VALID_EVENTS,
    STATUS_META: STATUS_META,
    REST_API_CATALOG: REST_API_CATALOG,
    SCENARIO_METADATA: SCENARIO_METADATA,
    generateUuidV4: generateUuidV4,
    isoUtc: isoUtc,
    predictChannels: predictChannels,
    explainRouting: explainRouting,
    buildEventPayload: buildEventPayload,
    buildRestErrorPreset: buildRestErrorPreset
  });
})(window);
