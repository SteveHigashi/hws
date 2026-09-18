(function () {
  "use strict";

  var script = document.currentScript;
  var KEY = script && script.getAttribute("data-key");
  var API_BASE = (script && script.getAttribute("data-api-base")) || "";
  var PAGEVIEW_API = (script && script.getAttribute("data-pageview-api")) || (API_BASE + "/api/collect/pageview");
  var BEHAVIOR_API = (script && script.getAttribute("data-behavior-api")) || (API_BASE + "/api/behavior/batch");

  if (!KEY) return;

  // ─── Owner opt-out ────────────────────────────────────────────────────────
  var OPT_OUT_KEY = "ha_optout";
  try {
    if (new URL(location.href).searchParams.get(OPT_OUT_KEY) === "1") {
      localStorage.setItem(OPT_OUT_KEY, "1");
    }
    if (localStorage.getItem(OPT_OUT_KEY) === "1") return;
  } catch (e) {}

  // ─── Session ID ───────────────────────────────────────────────────────────
  var SESSION_KEY = "ha_sid";
  function getSessionId() {
    var sid = sessionStorage.getItem(SESSION_KEY);
    if (!sid) {
      sid = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(SESSION_KEY, sid);
    }
    return sid;
  }

  // ─── UTM + anchor parsing ─────────────────────────────────────────────────
  function parseUtm(url) {
    try {
      var u = new URL(url);
      return {
        utm_source:   u.searchParams.get("utm_source"),
        utm_medium:   u.searchParams.get("utm_medium"),
        utm_campaign: u.searchParams.get("utm_campaign"),
        utm_content:  u.searchParams.get("utm_content"),
        utm_term:     u.searchParams.get("utm_term"),
        anchor:       u.hash ? u.hash.slice(1) : null,
      };
    } catch (e) { return {}; }
  }

  // ─── 404 detection ────────────────────────────────────────────────────────
  function detect404() {
    // Most sites set a meta tag or title for 404s; also check response status if available
    var meta = document.querySelector('meta[name="robots"][content*="noindex"]');
    var title = (document.title || "").toLowerCase();
    return !!(meta || title.indexOf("404") !== -1 || title.indexOf("not found") !== -1 || title.indexOf("page not found") !== -1);
  }

  // ─── Web Vitals ───────────────────────────────────────────────────────────
  var vitals = {};
  function observeVitals() {
    if (!window.PerformanceObserver) return;
    try {
      new PerformanceObserver(function (list) {
        list.getEntries().forEach(function (e) {
          if (e.name === "first-contentful-paint") vitals.fcp = Math.round(e.startTime);
        });
      }).observe({ type: "paint", buffered: true });
      new PerformanceObserver(function (list) {
        list.getEntries().forEach(function (e) { vitals.lcp = Math.round(e.startTime); });
      }).observe({ type: "largest-contentful-paint", buffered: true });
    } catch (e) {}
    var nav = performance.getEntriesByType("navigation")[0];
    if (nav) vitals.ttfb = Math.round(nav.responseStart);
  }
  observeVitals();

  // ─── Scroll tracking ──────────────────────────────────────────────────────
  var maxScroll = 0;
  var scrollPauseTimer = null;
  var lastScrollY = 0;
  var lastScrollTime = Date.now();

  window.addEventListener("scroll", function () {
    var pct = Math.round(((window.scrollY + window.innerHeight) / document.documentElement.scrollHeight) * 100);
    if (pct > maxScroll) maxScroll = pct;

    clearTimeout(scrollPauseTimer);
    var currentY = window.scrollY;
    var now = Date.now();
    scrollPauseTimer = setTimeout(function () {
      var pauseDuration = Date.now() - now;
      if (pauseDuration >= 1500) {
        queueBehavior({
          event_type: "scroll_pause",
          scroll_y: currentY,
          scroll_pct: Math.round(((currentY + window.innerHeight) / document.documentElement.scrollHeight) * 100),
          duration_ms: pauseDuration,
        });
      }
    }, 1500);
    lastScrollY = currentY;
    lastScrollTime = now;
  }, { passive: true });

  // ─── Click tracking ───────────────────────────────────────────────────────
  document.addEventListener("click", function (e) {
    var el = e.target;
    var tag = el.tagName ? el.tagName.toLowerCase() : "";
    var href = el.href || (el.closest && el.closest("a") ? el.closest("a").href : null);
    var isExternal = href && !href.startsWith(location.origin);

    queueBehavior({
      event_type: isExternal ? "external_click" : "click",
      x: Math.round(e.clientX),
      y: Math.round(e.clientY),
      x_pct: Math.round((e.clientX / window.innerWidth) * 100),
      y_pct: Math.round((e.clientY / window.innerHeight) * 100),
      element_tag: tag,
      element_id: el.id || null,
      element_class: (el.className && typeof el.className === "string") ? el.className.slice(0, 128) : null,
      element_text: (el.innerText || el.textContent || "").trim().slice(0, 64) || null,
      href: isExternal ? href : null,
      scroll_y: window.scrollY,
      scroll_pct: maxScroll,
    });
  }, true);

  // ─── Text selection ───────────────────────────────────────────────────────
  document.addEventListener("mouseup", function () {
    var sel = window.getSelection ? window.getSelection().toString().trim() : "";
    if (sel.length > 3) {
      queueBehavior({
        event_type: "select",
        selected_text: sel.slice(0, 512),
        scroll_pct: maxScroll,
      });
    }
  });

  // Copy event
  document.addEventListener("copy", function () {
    var sel = window.getSelection ? window.getSelection().toString().trim() : "";
    if (sel.length > 0) {
      queueBehavior({ event_type: "copy", selected_text: sel.slice(0, 512) });
    }
  });

  // ─── Tab visibility ───────────────────────────────────────────────────────
  var tabBlurTime = null;
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      tabBlurTime = Date.now();
      queueBehavior({ event_type: "tab_blur" });
      flushBehavior(); // flush on hide — user may not return
    } else {
      var away = tabBlurTime ? Date.now() - tabBlurTime : null;
      queueBehavior({ event_type: "tab_focus", duration_ms: away });
      tabBlurTime = null;
    }
  });

  // ─── Form field tracking ──────────────────────────────────────────────────
  var formFocusTimes = {};
  document.addEventListener("focusin", function (e) {
    var el = e.target;
    if (!el || !el.tagName) return;
    var tag = el.tagName.toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") {
      formFocusTimes[el.name || el.id || "unknown"] = Date.now();
      queueBehavior({
        event_type: "form_field",
        field_name: el.name || el.id || null,
        field_type: el.type || tag,
        field_action: "focus",
      });
    }
  }, true);

  document.addEventListener("focusout", function (e) {
    var el = e.target;
    if (!el || !el.tagName) return;
    var tag = el.tagName.toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") {
      var key = el.name || el.id || "unknown";
      var focusTime = formFocusTimes[key];
      var duration = focusTime ? Date.now() - focusTime : null;
      var hasValue = !!(el.value && el.value.trim());
      queueBehavior({
        event_type: "form_field",
        field_name: el.name || el.id || null,
        field_type: el.type || tag,
        field_action: hasValue ? "blur" : "abandon",
        duration_ms: duration,
      });
      delete formFocusTimes[key];
    }
  }, true);

  // ─── Media tracking ───────────────────────────────────────────────────────
  function attachMedia(el) {
    ["play", "pause", "ended"].forEach(function (evt) {
      el.addEventListener(evt, function () {
        queueBehavior({
          event_type: "media",
          media_src: (el.src || el.currentSrc || "").slice(0, 512),
          media_action: evt,
          media_position: Math.round(el.currentTime),
        });
      });
    });
  }
  document.querySelectorAll("audio, video").forEach(attachMedia);
  var mediaObserver = new MutationObserver(function (muts) {
    muts.forEach(function (m) {
      m.addedNodes.forEach(function (n) {
        if (n.tagName === "VIDEO" || n.tagName === "AUDIO") attachMedia(n);
      });
    });
  });
  mediaObserver.observe(document.body, { childList: true, subtree: true });

  // ─── JS Error tracking ────────────────────────────────────────────────────
  window.addEventListener("error", function (e) {
    queueBehavior({
      event_type: "error",
      error_message: (e.message || "").slice(0, 512),
      error_source: (e.filename || "").slice(0, 256),
      error_line: e.lineno || null,
    });
  });

  // Print
  window.addEventListener("beforeprint", function () {
    queueBehavior({ event_type: "print" });
  });

  // ─── Behavior queue + batch flush ─────────────────────────────────────────
  var behaviorQueue = [];
  var flushTimer = null;

  function queueBehavior(data) {
    behaviorQueue.push(Object.assign({
      tracker_key: KEY,
      session_id: getSessionId(),
      page_url: location.href,
    }, data));
    clearTimeout(flushTimer);
    flushTimer = setTimeout(flushBehavior, 3000); // flush after 3s quiet
    if (behaviorQueue.length >= 20) flushBehavior(); // or when queue hits 20
  }

  function flushBehavior() {
    if (!behaviorQueue.length) return;
    var batch = behaviorQueue.splice(0, 50);
    var body = JSON.stringify({ events: batch });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(BEHAVIOR_API, new Blob([body], { type: "application/json" }));
    } else {
      var xhr = new XMLHttpRequest();
      xhr.open("POST", BEHAVIOR_API, true);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.send(body);
    }
  }

  // ─── Pageview ─────────────────────────────────────────────────────────────
  var pageEnteredAt = Date.now();

  function sendPageview(overrides) {
    var utm = parseUtm(location.href);
    var payload = Object.assign({
      tracker_key: KEY,
      session_id: getSessionId(),
      page_url: location.href,
      page_title: document.title,
      referrer: document.referrer || null,
      screen_width: screen.width,
      screen_height: screen.height,
      language: navigator.language || null,
      scroll_depth: maxScroll,
      lcp: vitals.lcp || null,
      fcp: vitals.fcp || null,
      ttfb: vitals.ttfb || null,
      is_404: detect404(),
    }, utm, overrides);

    var body = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      navigator.sendBeacon(PAGEVIEW_API, new Blob([body], { type: "application/json" }));
    } else {
      var xhr = new XMLHttpRequest();
      xhr.open("POST", PAGEVIEW_API, true);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.send(body);
    }
  }

  // Send duration + flush behavior on unload
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      sendPageview({ duration_seconds: (Date.now() - pageEnteredAt) / 1000, scroll_depth: maxScroll });
      flushBehavior();
    }
  });

  // SPA navigation
  var _push = history.pushState;
  history.pushState = function () {
    _push.apply(this, arguments);
    setTimeout(function () {
      pageEnteredAt = Date.now();
      maxScroll = 0;
      sendPageview();
    }, 0);
  };
  window.addEventListener("popstate", function () {
    pageEnteredAt = Date.now();
    maxScroll = 0;
    sendPageview();
  });

  sendPageview();
})();
