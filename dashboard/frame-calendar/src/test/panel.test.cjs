const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const script = fs.readFileSync(path.join(__dirname, "../main/assets/frame-panel/panel.js"), "utf8");

async function run({ auth, savedAuth, origin = "https://ha.example", pathname = "/frame",
  panels = { frame: { title: "Frame" } }, dashboards = [], xray = false,
  connected = true, hidden = false, subscriptionFailure = false, discoveryFailure = false } = {}) {
  const messages = [];
  const stored = new Map(savedAuth ? [["hassTokens", JSON.stringify(savedAuth)]] : []);
  const state = { reloads: 0, assigned: null, subscription: null, ticks: null,
    connected, hidden, discoveryFailure, errors: [] };
  const connection = {
    subscribeEvents: async (callback, type) => {
      assert.equal(type, "lovelace_updated");
      if (subscriptionFailure) throw new Error("offline");
      state.subscription = callback;
      return () => {};
    },
    sendMessagePromise: async message => {
      if (state.discoveryFailure) throw new Error("offline");
      const wrap = value => xray ? { wrappedJSObject: value } : value;
      if (message.type === "get_panels") return wrap(panels);
      if (message.type === "lovelace/dashboards/list") return wrap(dashboards);
      assert.equal(message.type, "lovelace/config");
      assert.notEqual(message.url_path, "map", "Non-Lovelace panels must not be fetched as dashboards");
      return wrap({ views: [{}] });
    }
  };
  const root = { appendChild() {}, querySelectorAll: () => [] };
  vm.runInNewContext(script, {
    URL, Date, Map, WeakSet, console: { error: (...args) => state.errors.push(args) },
    browser: { runtime: { sendNativeMessage: async (app, message) => {
      assert.equal(app, "frame");
      messages.push(message);
      return message.type === "config"
        ? JSON.stringify({ url: "https://ha.example/frame", auth: auth || {} }) : null;
    } } },
    localStorage: { getItem: key => stored.get(key), setItem: (key, value) => stored.set(key, value) },
    location: { origin, pathname, reload: () => state.reloads++, assign: url => { state.assigned = url; } },
    document: {
      get hidden() { return state.hidden; }, documentElement: root,
      createElement: () => ({}), addEventListener() {},
      querySelector: () => ({ wrappedJSObject: { hass: { connection, connected: state.connected } } })
    },
    window: {}, exportFunction: callback => callback, cloneInto: value => value,
    setInterval: callback => { state.ticks = callback; }
  });
  await new Promise(resolve => setImmediate(resolve));
  return { state, stored, messages };
}

test("only the currently displayed dashboard's edits reload the panel", async () => {
  const { state } = await run();
  assert.ok(state.subscription);
  state.subscription({ data: { url_path: "other-dashboard" } });
  assert.equal(state.reloads, 0);
  state.subscription({ data: { url_path: "frame" } });
  assert.equal(state.reloads, 1);
});

test("an existing authorized login is not overwritten", async () => {
  const savedAuth = { refresh_token: "existing-test-token", clientId: "https://ha.example/" };
  const { state, stored, messages } = await run({
    auth: { refresh_token: "replacement-test-token" }, savedAuth
  });
  assert.equal(JSON.parse(stored.get("hassTokens")).refresh_token, savedAuth.refresh_token);
  assert.equal(state.reloads, 0);
  assert.ok(messages.some(message => message.type === "auth"));
});

test("a newly provisioned login is installed once before reloading", async () => {
  const auth = { refresh_token: "fixture-token", clientId: "https://ha.example/" };
  const { state, stored } = await run({ auth });
  assert.equal(state.reloads, 1);
  assert.deepEqual(JSON.parse(stored.get("hassTokens")), auth);
});

test("configuration is ignored on an unrelated origin", async () => {
  const { state, stored } = await run({
    origin: "https://unrelated.example", auth: { refresh_token: "fixture-token" }
  });
  assert.equal(state.ticks, null);
  assert.equal(stored.size, 0);
  assert.equal(state.reloads, 0);
});

test("a newly available Frame panel is selected automatically", async () => {
  const { state } = await run({ pathname: "/dashboard-panel/0" });
  assert.equal(state.assigned, "/frame");
});

test("non-Lovelace panels do not prevent reporting a missing Frame dashboard", async () => {
  const { messages } = await run({
    pathname: "/dashboard-panel/0",
    panels: {
      "dashboard-panel": { title: "Panel", component_name: "lovelace" },
      map: { title: "Map", component_name: "map" }
    },
    dashboards: [{ url_path: "map" }, { url_path: "dashboard-panel" }]
  });

  assert.ok(messages.some(message => message.text === "Panel - Frame not found; create it in Home Assistant"));
});

test("Firefox Xray-wrapped responses and events are copied before accessing fields", async () => {
  const { state } = await run({ xray: true, pathname: "/dashboard-panel/0" });
  assert.equal(state.assigned, "/frame");
  state.subscription({ wrappedJSObject: { data: { url_path: "dashboard-panel" } } });
  assert.equal(state.reloads, 1);
});

test("the panel keeps monitoring updates while hidden behind the screensaver", async () => {
  const { state, messages } = await run({ hidden: true });
  assert.ok(messages.some(message => message.state === "ready"));
  state.subscription({ data: { url_path: "frame" } });
  assert.equal(state.reloads, 1);
});

test("a disconnected panel reports a retryable state until it reconnects", async () => {
  const { state, messages } = await run({ connected: false });
  assert.ok(messages.some(message => message.state === "connecting"));
  assert.ok(!messages.some(message => message.state === "ready"));
  state.connected = true;
  state.ticks();
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(messages.some(message => message.state === "ready"));
});

test("an update subscription failure is not reported as a live panel", async () => {
  const { state, messages } = await run({ subscriptionFailure: true });
  state.ticks();
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(messages.some(message => message.state === "connecting"
    && message.text.includes("subscription failed")));
  assert.ok(!messages.some(message => message.state === "ready"));
  assert.ok(state.errors.length > 0);
});

test("a failed dashboard discovery remains retryable until it succeeds", async () => {
  const { state, messages } = await run({ discoveryFailure: true });
  assert.ok(messages.some(message => message.state === "connecting"
    && message.text.includes("discovery failed")));
  assert.ok(!messages.some(message => message.state === "ready"));
  state.discoveryFailure = false;
  state.ticks();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(messages.at(-1).state, "ready");
});

test("a fallback dashboard reports recovery after the connection returns", async () => {
  const { state, messages } = await run({
    pathname: "/dashboard-panel/0",
    panels: { "dashboard-panel": { title: "Panel", component_name: "lovelace" } },
    dashboards: [{ url_path: "dashboard-panel" }]
  });
  assert.equal(messages.at(-1).state, "ready");
  state.connected = false;
  state.ticks();
  assert.equal(messages.at(-1).state, "connecting");
  state.connected = true;
  state.ticks();
  assert.equal(messages.at(-1).state, "ready");
});

test("a sign-in page is reported separately from retryable connection errors", async () => {
  const { messages } = await run({ pathname: "/auth/authorize", connected: false });
  assert.ok(messages.some(message => message.state === "login"));
  assert.ok(!messages.some(message => message.state === "ready"));
});
