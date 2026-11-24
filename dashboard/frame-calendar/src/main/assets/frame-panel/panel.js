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
  let discoveredFrame = false;
  let discoveryRunning = false;
  let lastDiscovery = 0;
  let lastStatus = "";
  const report = text => {
    if (text !== lastStatus) {
      lastStatus = text;
      send({ type: "status", text }).catch(console.error);
    }
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
      const panels = await hass.connection.sendMessagePromise(cloneInto({ type: "get_panels" }, window));
      const frame = Object.entries(panels).find(([path, panel]) =>
        path.toLowerCase() === "frame" || panel.title?.toLowerCase() === "frame");
      if (frame) {
        discoveredFrame = true;
        const target = "/" + frame[0];
        if (location.pathname.split("/")[1] !== frame[0]) location.assign(target);
        report("Frame - live");
      } else {
        const path = location.pathname.split("/")[1];
        const dashboards = await hass.connection.sendMessagePromise(
          cloneInto({ type: "lovelace/dashboards/list" }, window));
        for (const dashboard of dashboards) {
          if (panels[dashboard.url_path]?.component_name !== "lovelace") continue;
          const lovelace = await hass.connection.sendMessagePromise(
            cloneInto({ type: "lovelace/config", url_path: dashboard.url_path }, window));
          const index = lovelace.views.findIndex(view =>
            view.title?.toLowerCase() === "frame" || view.path?.toLowerCase() === "frame");
          if (index < 0) continue;
          discoveredFrame = true;
          const target = "/" + dashboard.url_path + "/" + (lovelace.views[index].path ?? index);
          if (location.pathname !== target) location.assign(target);
          report("Frame - live");
          return;
        }
        discoveredFrame = false;
        const label = panels[path]?.title || "Home Assistant";
        report(label + " - Frame not found; create it in Home Assistant");
      }
    } catch (error) {
      report("Frame discovery failed - check Home Assistant permissions");
      console.error("Frame dashboard discovery failed", error);
    } finally {
      discoveryRunning = false;
    }
  }
  function tick() {
    if (document.hidden) return;
    if (document.documentElement) style(document.documentElement);
    const auth = localStorage.getItem("hassTokens");
    if (auth && auth !== lastAuth) {
      try {
        send({ type: "auth", auth: JSON.parse(auth) }).catch(console.error);
        lastAuth = auth;
      } catch (error) {
        report("Home Assistant login could not be read - sign in again");
      }
    }
    const app = document.querySelector("home-assistant");
    const hass = app?.wrappedJSObject?.hass;
    if (!hass?.connection) {
      report("Home Assistant - sign in or reconnect");
      return;
    }
    // Home Assistant exposes its authenticated, reconnecting websocket to the
    // frontend; subscribe to the same event as the official Lovelace frontend.
    if (connection !== hass.connection) {
      if (unsubscribe) unsubscribe();
      connection = hass.connection;
      const changed = exportFunction(event => {
        const dashboard = location.pathname.split("/")[1];
        if (event.data.url_path === dashboard || (!event.data.url_path && dashboard === "lovelace")) {
          location.reload();
        }
      }, window);
      connection.subscribeEvents(changed, "lovelace_updated")
        .then(exportFunction(remove => { unsubscribe = remove; }, window))
        .catch(exportFunction(error => {
          connection = undefined;
          report("Panel update subscription failed - Reload to retry");
          console.error(error);
        }, window));
      lastDiscovery = 0;
    }
    discoverFrame(hass);
    if (discoveredFrame) report("Frame - live");
  }
  setInterval(tick, 3000);
  document.addEventListener("visibilitychange", tick);
  tick();
})().catch(error => console.error("Frame panel integration failed", error));
