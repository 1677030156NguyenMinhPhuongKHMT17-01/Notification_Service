const fs = require("fs");
const path = require("path");
const Ajv2020 = require("ajv/dist/2020");
const addFormats = require("ajv-formats");

const root = path.resolve(__dirname, "..");
const schemaDir = path.join(root, "schema");
const validDir = path.join(root, "samples", "valid");
const invalidDir = path.join(root, "samples", "invalid");

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);

const createdSchema = readJson(path.join(schemaDir, "alert.created.schema.json"));
const escalatedSchema = readJson(path.join(schemaDir, "alert.escalated.schema.json"));
const resolvedSchema = readJson(path.join(schemaDir, "alert.resolved.schema.json"));
const topicSchema = readJson(path.join(schemaDir, "campus.alerts.schema.json"));

ajv.addSchema(createdSchema);
ajv.addSchema(escalatedSchema);
ajv.addSchema(resolvedSchema);

const validatorsByEvent = {
  "alert.created": ajv.getSchema(createdSchema.$id),
  "alert.escalated": ajv.getSchema(escalatedSchema.$id),
  "alert.resolved": ajv.getSchema(resolvedSchema.$id)
};
const validateTopic = ajv.compile(topicSchema);

function validatePayload(payload) {
  const specificValidator = validatorsByEvent[payload.event_name] || validatorsByEvent["alert.created"];
  const specificOk = specificValidator(payload);
  const topicOk = validateTopic(payload);
  return {
    ok: Boolean(specificOk && topicOk),
    errors: specificValidator.errors || validateTopic.errors
  };
}

let failed = 0;

for (const name of fs.readdirSync(validDir).sort()) {
  if (!name.endsWith(".json")) continue;
  const payload = readJson(path.join(validDir, name));
  const result = validatePayload(payload);
  console.log(result.ok ? `[PASS] ${name}` : `[FAIL] ${name}`);
  if (!result.ok) {
    console.log(result.errors);
    failed++;
  }
}

for (const name of fs.readdirSync(invalidDir).sort()) {
  if (!name.endsWith(".json")) continue;
  const payload = readJson(path.join(invalidDir, name));
  const result = validatePayload(payload);
  console.log(!result.ok ? `[PASS expected-invalid] ${name}` : `[FAIL unexpected-valid] ${name}`);
  if (result.ok) {
    failed++;
  }
}

// Level B — Consumer Semantic Stub Tests (Q05–Q09)
class NotificationConsumerStub {
  constructor() {
    this.processedEventIds = new Set();
    this.alertLatestStatus = new Map(); // alert_id -> { status, timestamp }
    this.sentNotifications = [];
    this.dlqMessages = [];
    this.maxRetries = 3;
    this.retryIntervalSeconds = 5;
  }

  resolveChannels(event) {
    if (Array.isArray(event.target_channels) && event.target_channels.length > 0) {
      return event.target_channels;
    }
    const map = {
      low: ["email"],
      medium: ["telegram", "email"],
      high: ["telegram", "email", "discord"],
      critical: ["telegram", "email", "discord", "sms"]
    };
    return map[event.severity] || ["telegram", "email"];
  }

  consume(event, options = {}) {
    const schemaCheck = validatePayload(event);
    if (!schemaCheck.ok) {
      this.dlqMessages.push({
        topic: "campus.alerts.dlq",
        reason: "SCHEMA_VALIDATION_FAILED",
        retry_count: 0,
        event
      });
      return { status: "REJECTED_TO_DLQ", reason: "SCHEMA_VALIDATION_FAILED" };
    }

    // Q05: Idempotency / Deduplication by event_id
    if (this.processedEventIds.has(event.event_id)) {
      return { status: "DUPLICATE_EVENT_SKIPPED", event_id: event.event_id };
    }

    // Q09: Out-of-order check (e.g., alert.created arriving after a newer alert.resolved)
    const eventTime = Date.parse(event.timestamp);
    const current = this.alertLatestStatus.get(event.alert_id);
    if (current && current.status === "RESOLVED" && event.event_name !== "alert.resolved" && eventTime < current.timestamp) {
      this.processedEventIds.add(event.event_id);
      return { status: "SUPPRESSED_OUT_OF_ORDER", alert_id: event.alert_id };
    }

    // Q06 & Q07: Retry policy (max 3 retries, 5s interval) & DLQ on failure
    const failTimes = options.simulateTransientFailures || 0;
    let attempts = 0;
    while (attempts <= this.maxRetries) {
      attempts++;
      if (attempts <= failTimes) {
        continue;
      }
      this.processedEventIds.add(event.event_id);
      this.alertLatestStatus.set(event.alert_id, {
        status: event.event_name === "alert.resolved" ? "RESOLVED" : "OPEN",
        timestamp: eventTime
      });
      const channels = this.resolveChannels(event);
      this.sentNotifications.push({ event_id: event.event_id, alert_id: event.alert_id, channels, attempts });
      return { status: "SENT", attempts, channels };
    }

    this.dlqMessages.push({
      topic: "campus.alerts.dlq",
      reason: "MAX_RETRIES_EXCEEDED",
      retry_count: this.maxRetries,
      retry_interval_seconds: this.retryIntervalSeconds,
      event
    });
    return { status: "MOVED_TO_DLQ", attempts: this.maxRetries };
  }
}

const consumer = new NotificationConsumerStub();
const validSample = readJson(path.join(validDir, "alert-created-valid.json"));
const resolvedSample = readJson(path.join(validDir, "alert-resolved-valid.json"));

// Q05: Duplicate event_id test
const firstRun = consumer.consume(validSample);
const secondRun = consumer.consume(validSample);
const q05Ok = firstRun.status === "SENT" && secondRun.status === "DUPLICATE_EVENT_SKIPPED" && consumer.sentNotifications.length === 1;
console.log(q05Ok ? "[PASS semantic-stub] Q05-duplicate-eventId-idempotency" : "[FAIL semantic-stub] Q05-duplicate-eventId-idempotency");
if (!q05Ok) failed++;

// Q06: Transient error succeeds within 3 retries
const retryEvent = { ...validSample, event_id: "123e4567-e89b-12d3-a456-426614174050", alert_id: "ALT-050" };
const retryRun = consumer.consume(retryEvent, { simulateTransientFailures: 2 });
const q06Ok = retryRun.status === "SENT" && retryRun.attempts === 3;
console.log(q06Ok ? "[PASS semantic-stub] Q06-consumer-retry-within-limit" : "[FAIL semantic-stub] Q06-consumer-retry-within-limit");
if (!q06Ok) failed++;

// Q07: Exhausted 3 retries routes to campus.alerts.dlq
const dlqEvent = { ...validSample, event_id: "123e4567-e89b-12d3-a456-426614174051", alert_id: "ALT-051" };
const dlqRun = consumer.consume(dlqEvent, { simulateTransientFailures: 4 });
const q07Ok = dlqRun.status === "MOVED_TO_DLQ" && consumer.dlqMessages.some((m) => m.event.event_id === dlqEvent.event_id && m.topic === "campus.alerts.dlq");
console.log(q07Ok ? "[PASS semantic-stub] Q07-dlq-after-3-retries" : "[FAIL semantic-stub] Q07-dlq-after-3-retries");
if (!q07Ok) failed++;

// Q08: Unsupported event_name / version rejected to DLQ
const unsupportedEvent = readJson(path.join(invalidDir, "invalid-event-name.json"));
const q08Run = consumer.consume(unsupportedEvent);
const q08Ok = q08Run.status === "REJECTED_TO_DLQ" && q08Run.reason === "SCHEMA_VALIDATION_FAILED";
console.log(q08Ok ? "[PASS semantic-stub] Q08-unsupported-event-rejected" : "[FAIL semantic-stub] Q08-unsupported-event-rejected");
if (!q08Ok) failed++;

// Q09: Out-of-order event (alert.resolved arrives before older alert.created)
const oooResolved = {
  ...resolvedSample,
  event_id: "123e4567-e89b-12d3-a456-426614174060",
  alert_id: "ALT-060",
  timestamp: "2026-08-27T17:00:00Z"
};
const oooLateCreated = {
  ...validSample,
  event_id: "123e4567-e89b-12d3-a456-426614174061",
  alert_id: "ALT-060",
  timestamp: "2026-08-27T16:50:00Z"
};
consumer.consume(oooResolved);
const oooRun = consumer.consume(oooLateCreated);
const q09Ok = oooRun.status === "SUPPRESSED_OUT_OF_ORDER";
console.log(q09Ok ? "[PASS semantic-stub] Q09-out-of-order-event-suppressed" : "[FAIL semantic-stub] Q09-out-of-order-event-suppressed");
if (!q09Ok) failed++;

process.exitCode = failed === 0 ? 0 : 1;

