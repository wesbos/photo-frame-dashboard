/* global browser, exportFunction, cloneInto */
(async () => {
  const send = message => browser.runtime.sendNativeMessage("frame", message);
  // Native code checks the session, top-level frame and configured origin before
  // releasing configuration. Never expose an existing login to another origin.
  const reply = await send({ type: "config" });
  const config = reply ? JSON.parse(reply) : null;
  if (!config || new URL(config.url).origin !== location.origin) return;
  if (config.auth?.refresh_token && !localStorage.getItem("hassTokens")) {
    localStorage.setItem("hassTokens", JSON.stringify(config.auth));
    location.reload();
    return;
  }
  localStorage.setItem("selectedTheme", JSON.stringify({ theme: "default", dark: true }));
  let lastAuth = "";
  let connection;
  let unsubscribe;
  let dashboardStatus = "";
  let subscriptionHealthy = false;
  let discoveryHealthy = false;
  let discoveryRunning = false;
  let lastDiscovery = 0;
  let lastStatus = "";
  let lastState = "";
  function copyJson(value) {
    return JSON.parse(JSON.stringify(value?.wrappedJSObject || value));
  }
  async function request(hass, message) {
    // Promise results cross Firefox's Xray boundary. Copy JSON into the
    // extension realm before reading fields or calling array methods.
    return copyJson(await hass.connection.sendMessagePromise(cloneInto(message, window)));
  }
  const report = (text, state) => {
    if (text !== lastStatus || state !== lastState) {
      lastStatus = text;
      lastState = state;
      send({ type: "status", text, state }).catch(console.error);
    }
  };
  const reportDashboard = text => {
    dashboardStatus = text;
    discoveryHealthy = true;
    if (subscriptionHealthy) report(text, "ready");
  };
  const css = `
    :host, html {
      color-scheme: dark !important;
      --primary-background-color: #1e1e2e !important;
      --secondary-background-color: #181825 !important;
      --card-background-color: #313244 !important;
      --ha-card-background: #313244 !important;
      --primary-text-color: #cdd6f4 !important;
      --secondary-text-color: #a6adc8 !important;
      --divider-color: #45475a !important;
      --primary-color: #cba6f7 !important;
      --app-header-background-color: #1e1e2e !important;
    }
    html, body { background: #1e1e2e !important; color: #cdd6f4 !important; }
    ha-sidebar { display: none !important; }
    ha-app-layout { --app-layout-header-height: 0px !important; }
    hui-masonry-view { --masonry-view-card-margin: 6px !important; }
    ha-card { border-color: #45475a !important; }
  `;
  const styled = new WeakSet();
  function style(root) {
    if (!styled.has(root)) {
      const sheet = document.createElement("style");
      sheet.textContent = css;
      if (root.host?.localName === "hui-root") {
        sheet.textContent += ".header, .toolbar, app-toolbar { display: none !important; }";
      }
      root.appendChild(sheet);
      styled.add(root);
    }
    for (const node of root.querySelectorAll("*")) {
      if (node.shadowRoot) style(node.shadowRoot);
    }
  }
  async function discoverFrame(hass) {
    if (discoveryRunning || Date.now() - lastDiscovery < 60000) return;
    discoveryRunning = true;
    lastDiscovery = Date.now();
    try {
      const panels = await request(hass, { type: "get_panels" });
      const frame = Object.entries(panels).find(([path, panel]) =>
        path.toLowerCase() === "frame" || panel.title?.toLowerCase() === "frame");
      if (frame) {
        const target = "/" + frame[0];
        if (location.pathname.split("/")[1] !== frame[0]) location.assign(target);
        reportDashboard("Frame - live");
      } else {
        const path = location.pathname.split("/")[1];
        const dashboards = await request(hass, { type: "lovelace/dashboards/list" });
        for (const dashboard of dashboards) {
          if (panels[dashboard.url_path]?.component_name !== "lovelace") continue;
          const lovelace = await request(hass, { type: "lovelace/config", url_path: dashboard.url_path });
          if (!Array.isArray(lovelace.views)) {
            if (lovelace.strategy) continue;
            throw new Error("Home Assistant returned a dashboard without views");
          }
          const index = lovelace.views.findIndex(view =>
            view.title?.toLowerCase() === "frame" || view.path?.toLowerCase() === "frame");
          if (index < 0) continue;
          const target = "/" + dashboard.url_path + "/" + (lovelace.views[index].path ?? index);
          if (location.pathname !== target) location.assign(target);
          reportDashboard("Frame - live");
          return;
        }
        const label = panels[path]?.title || "Home Assistant";
        reportDashboard(label + " - Frame not found; create it in Home Assistant");
      }
    } catch (error) {
      discoveryHealthy = false;
      lastDiscovery = 0;
      report("Frame discovery failed: " + (error?.message || error?.name || "connection error"), "connecting");
      console.error("Frame dashboard discovery failed", error);
    } finally {
      discoveryRunning = false;
    }
  }
  function tick() {
    if (document.documentElement) style(document.documentElement);
    const auth = localStorage.getItem("hassTokens");
    if (auth && auth !== lastAuth) {
      try {
        send({ type: "auth", auth: JSON.parse(auth) }).catch(console.error);
        lastAuth = auth;
      } catch (error) {
        report("Home Assistant login could not be read - sign in again", "login");
      }
    }
    const app = document.querySelector("home-assistant");
    const hass = app?.wrappedJSObject?.hass;
    if (!hass?.connection || hass.connected === false) {
      const login = location.pathname.startsWith("/auth/");
      report(login ? "Home Assistant - sign in" : "Home Assistant - sign in or reconnect",
        login ? "login" : "connecting");
      return;
    }
    // Home Assistant exposes its authenticated, reconnecting websocket to the
    // frontend; subscribe to the same event as the official Lovelace frontend.
    if (connection !== hass.connection) {
      if (unsubscribe) unsubscribe();
      connection = hass.connection;
      subscriptionHealthy = false;
      const changed = exportFunction(value => {
        const event = copyJson(value);
        const dashboard = location.pathname.split("/")[1];
        if (event.data.url_path === dashboard || (!event.data.url_path && dashboard === "lovelace")) {
          location.reload();
        }
      }, window);
      connection.subscribeEvents(changed, "lovelace_updated")
        .then(exportFunction(remove => {
          unsubscribe = remove.wrappedJSObject || remove;
          subscriptionHealthy = true;
          if (discoveryHealthy && dashboardStatus) report(dashboardStatus, "ready");
        }, window))
        .catch(exportFunction(error => {
          connection = undefined;
          subscriptionHealthy = false;
          report("Panel update subscription failed - retrying", "connecting");
          console.error(error);
        }, window));
      lastDiscovery = 0;
    }
    discoverFrame(hass);
    if (discoveryHealthy && dashboardStatus) reportDashboard(dashboardStatus);
  }
  setInterval(tick, 3000);
  document.addEventListener("visibilitychange", tick);
  tick();
})().catch(error => console.error("Frame panel integration failed", error));
