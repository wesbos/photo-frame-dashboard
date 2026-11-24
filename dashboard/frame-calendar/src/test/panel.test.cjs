const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const script = fs.readFileSync(path.join(__dirname, "../main/assets/frame-panel/panel.js"), "utf8");

async function run({ auth, savedAuth, origin = "https://ha.example", pathname = "/frame",
  panels = { frame: { title: "Frame" } }, dashboards = [] } = {}) {
  const messages = [];
  const stored = new Map(savedAuth ? [["hassTokens", JSON.stringify(savedAuth)]] : []);
  const state = { reloads: 0, assigned: null, subscription: null, ticks: null };
  const connection = {
    subscribeEvents: async (callback, type) => {
      assert.equal(type, "lovelace_updated");
      state.subscription = callback;
      return () => {};
    },
    sendMessagePromise: async message => {
      if (message.type === "get_panels") return panels;
      if (message.type === "lovelace/dashboards/list") return dashboards;
      assert.equal(message.type, "lovelace/config");
      assert.notEqual(message.url_path, "map", "Non-Lovelace panels must not be fetched as dashboards");
      return { views: [{}] };
    }
  };
  const root = { appendChild() {}, querySelectorAll: () => [] };
  vm.runInNewContext(script, {
    URL, Date, Map, WeakSet, console,
    browser: { runtime: { sendNativeMessage: async (app, message) => {
      assert.equal(app, "frame");
      messages.push(message);
      return message.type === "config"
        ? JSON.stringify({ url: "https://ha.example/frame", auth: auth || {} }) : null;
    } } },
    localStorage: { getItem: key => stored.get(key), setItem: (key, value) => stored.set(key, value) },
    location: { origin, pathname, reload: () => state.reloads++, assign: url => { state.assigned = url; } },
    document: {
      hidden: false, documentElement: root,
      createElement: () => ({}), addEventListener() {},
      querySelector: () => ({ wrappedJSObject: { hass: { connection } } })
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
