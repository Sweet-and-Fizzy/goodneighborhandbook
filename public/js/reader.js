/* The online handbook reader. Without this script the pages on /read/ simply
   stack and scroll; with it they become a book you page through. */
(function () {
  "use strict";

  var root = document.documentElement;
  // One page at a time unless the screen is wide enough for two readable pages.
  var singleQuery = window.matchMedia("(max-width: 68rem)");

  // Set these straight away, before the page is drawn, so the stacked pages never flash.
  root.classList.add("js-reader");
  root.classList.toggle("is-single", singleQuery.matches);

  // If anything below goes wrong, fall back to the plain stacked pages rather
  // than leaving an empty book.
  function fallBack() { root.classList.remove("js-reader", "is-single"); }
  function boot() {
    try { start(); } catch (err) {
      fallBack();
      if (window.console) console.error(err);
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  function start() {
    var book = document.getElementById("book");
    var viewport = document.getElementById("reader-viewport");
    var wrap = document.getElementById("reader-wrap");
    var prevBtn = document.getElementById("reader-prev");
    var nextBtn = document.getElementById("reader-next");
    var status = document.getElementById("reader-status");
    if (!book || !viewport || !wrap || !prevBtn || !nextBtn || !status) { fallBack(); return; }

    // These are optional: the reader still works if one is missing.
    var main = document.getElementById("main");
    var controls = document.getElementById("reader-controls");
    var slider = document.getElementById("reader-slider");
    var toc = document.getElementById("reader-toc");
    var fullBtn = document.getElementById("reader-full");
    var zoomInBtn = document.getElementById("reader-zoom-in");
    var zoomOutBtn = document.getElementById("reader-zoom-out");

    var pages = Array.prototype.slice.call(book.querySelectorAll(".page"));
    var total = pages.length;
    if (!total) { fallBack(); return; }
    var images = pages.map(function (p) { return p.querySelector("img"); });
    var normalSizes = images.map(function (img) { return img.sizes; });

    var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    var ZOOMS = [1, 1.5, 2, 3]; // matches the .zoom-1 to .zoom-3 rules in reader.css
    var single = singleQuery.matches;
    var current = 1;        // the page being read (in a spread, either page of it)
    var zoom = 0;           // index into ZOOMS
    var finishTurn = null;  // set while a page is turning; call it to finish at once
    var started = false;

    function clamp(n) { return Math.min(total, Math.max(1, n)); }

    // Page 1 sits alone on the right; after that even pages are on the left.
    function spreadOf(n) {
      var left = n % 2 === 0 ? n : n - 1;
      return { left: left >= 1 ? left : null, right: left + 1 <= total ? left + 1 : null };
    }
    function page(n) { return n ? pages[n - 1] : null; }
    function visible() {
      if (single) return [current];
      var s = spreadOf(current);
      return [s.left, s.right].filter(Boolean);
    }

    // Images are lazy; fetch the ones a page turn away so turns are not blank.
    function preload(n) {
      for (var i = clamp(n - 4); i <= clamp(n + 5); i++) images[i - 1].loading = "eager";
    }

    // When zoomed, ask for the large page image whatever the screen size.
    function chooseImages() {
      var shown = visible();
      images.forEach(function (img, i) {
        var want = zoom && shown.indexOf(i + 1) !== -1 ? "300vw" : normalSizes[i];
        if (img.sizes !== want) img.sizes = want;
      });
    }

    function setDisabled(btn, off) {
      // aria-disabled rather than disabled, so the button keeps keyboard focus.
      btn.setAttribute("aria-disabled", off ? "true" : "false");
    }

    function render() {
      var shown = visible();
      var first = shown[0], last = shown[shown.length - 1];
      pages.forEach(function (p) { p.classList.remove("is-left", "is-right", "is-current"); });
      if (single) {
        page(current).classList.add("is-current");
      } else {
        var s = spreadOf(current);
        if (s.left) page(s.left).classList.add("is-left");
        if (s.right) page(s.right).classList.add("is-right");
      }

      var text = (first === last ? "Page " + first : "Pages " + first + "–" + last) + " of " + total;
      if (status.textContent !== text) status.textContent = text;
      setDisabled(prevBtn, first <= 1);
      setDisabled(nextBtn, last >= total);

      if (slider) {
        // In a spread the slider moves two pages at a time (0 stands for the cover).
        slider.min = single ? 1 : 0;
        slider.step = single ? 1 : 2;
        slider.value = single ? current : (spreadOf(current).left || 0);
        slider.setAttribute("aria-valuetext", text);
      }
      if (toc) {
        // Show the section being read.
        var section = "";
        Array.prototype.forEach.call(toc.options, function (o) {
          if (parseInt(o.value, 10) <= last) section = o.value;
        });
        if (section) toc.value = section;
      }

      preload(current);
      chooseImages();
      wake();
      // Keep the address in step with the page, but not on first load: a "#p1"
      // there would make the browser scroll down to the book.
      if (started && window.history && history.replaceState) history.replaceState(null, "", "#p" + first);
      started = true;
    }

    function face(n, cls) {
      var el = document.createElement("div");
      el.className = "leaf__face " + cls;
      if (n) {
        var img = images[n - 1].cloneNode(false);
        img.loading = "eager";
        img.alt = "";
        el.appendChild(img);
      }
      return el;
    }

    // Turn one leaf between two neighbouring spreads.
    function turn(from, to, target) {
      var forward = (to.left || 0) > (from.left || 0);
      var leaf = document.createElement("div");
      leaf.className = "leaf";
      leaf.setAttribute("aria-hidden", "true");
      // The leaf's front is the right-hand page of the earlier spread and its
      // back is the left-hand page of the later one.
      var earlier = forward ? from : to;
      var later = forward ? to : from;
      leaf.appendChild(face(earlier.right, "leaf__face--front"));
      leaf.appendChild(face(later.left, "leaf__face--back"));

      if (forward) {
        if (from.right) page(from.right).classList.remove("is-right");
        if (to.right) page(to.right).classList.add("is-right");
      } else {
        leaf.classList.add("no-anim", "is-turned");
        if (from.left) page(from.left).classList.remove("is-left");
        if (to.left) page(to.left).classList.add("is-left");
      }
      book.appendChild(leaf);
      void leaf.offsetWidth; // let the starting position apply before animating
      leaf.classList.remove("no-anim");
      leaf.classList.toggle("is-turned", forward);

      var timer = window.setTimeout(finish, 900);
      function finish() {
        if (finishTurn !== finish) return;
        finishTurn = null;
        window.clearTimeout(timer);
        current = target;
        render();
        leaf.remove();
      }
      finishTurn = finish;
      leaf.addEventListener("transitionend", function (e) { if (e.target === leaf) finish(); });
    }

    function go(n, animate) {
      if (isNaN(n)) return;
      n = clamp(n);
      if (finishTurn) finishTurn(); // a new request ends the turn in progress
      var from = spreadOf(current);
      var to = spreadOf(n);
      var sameView = single ? n === current : from.left === to.left;
      if (sameView) { current = n; render(); return; }
      var adjacent = Math.abs((to.left || 0) - (from.left || 0)) === 2;
      if (animate && adjacent && !single && !zoom && !reduceMotion.matches) {
        turn(from, to, n);
      } else {
        current = n;
        render();
        if (zoom) { viewport.scrollLeft = 0; viewport.scrollTop = 0; } // start of the new page
      }
    }

    function next() {
      if (finishTurn) finishTurn(); // so a quick second press starts from the new page
      var shown = visible();
      go(shown[shown.length - 1] + 1, true);
    }
    function prev() {
      if (finishTurn) finishTurn();
      go(visible()[0] - 1, true);
    }

    // ---- the control bar ----
    // The bar lies over the bottom of the stage. Where it covers part of the
    // book it fades out after a moment, and any movement brings it back.
    var idleTimer = null;
    function wake() {
      if (!main || !controls) return;
      main.classList.remove("reader--idle");
      window.clearTimeout(idleTimer);
      idleTimer = window.setTimeout(function () {
        var covering = controls.getBoundingClientRect().top < viewport.getBoundingClientRect().bottom - 1;
        if (!covering) return;
        if (controls.contains(document.activeElement) || controls.matches(":hover")) { wake(); return; }
        main.classList.add("reader--idle");
      }, 2500);
    }
    if (main) ["pointermove", "pointerdown", "keydown", "focusin"].forEach(function (name) {
      main.addEventListener(name, wake, { passive: true });
    });
    window.addEventListener("resize", wake);

    function fromHash() {
      var m = /^#p(\d+)$/.exec(window.location.hash);
      return m ? clamp(parseInt(m[1], 10)) : null;
    }

    // ---- zoom ----
    // Change zoom level, keeping the point (cx, cy) of the viewport where it
    // is on the page. The point is in viewport pixels; the centre by default.
    function setZoom(level, cx, cy) {
      level = Math.min(ZOOMS.length - 1, Math.max(0, level));
      if (level === zoom) return;
      if (finishTurn) finishTurn();
      if (cx === undefined) { cx = viewport.clientWidth / 2; cy = viewport.clientHeight / 2; }
      var fx = (viewport.scrollLeft + cx) / book.offsetWidth;
      var fy = (viewport.scrollTop + cy) / book.offsetHeight;
      if (zoom) viewport.classList.remove("zoom-" + zoom);
      zoom = level;
      viewport.classList.toggle("is-zoomed", zoom > 0);
      if (zoom) viewport.classList.add("zoom-" + zoom);
      viewport.scrollLeft = fx * book.offsetWidth - cx;
      viewport.scrollTop = fy * book.offsetHeight - cy;
      if (zoomOutBtn) zoomOutBtn.disabled = zoom === 0;
      if (zoomInBtn) zoomInBtn.disabled = zoom === ZOOMS.length - 1;
      chooseImages();
      wake();
    }
    function onLink(el) { return el && el.closest && el.closest(".hot, .hot-group"); }

    if (zoomInBtn) zoomInBtn.addEventListener("click", function () { setZoom(zoom + 1); });
    if (zoomOutBtn) zoomOutBtn.addEventListener("click", function () { setZoom(zoom - 1); });
    viewport.addEventListener("dblclick", function (e) {
      if (onLink(e.target)) return;
      var r = viewport.getBoundingClientRect();
      setZoom(zoom ? 0 : 2, e.clientX - r.left, e.clientY - r.top);
    });

    // Drag with the mouse to move around a zoomed page.
    var drag = null;
    function endDrag() {
      drag = null;
      viewport.classList.remove("is-dragging");
    }
    viewport.addEventListener("mousedown", function (e) {
      if (!zoom || e.button !== 0 || onLink(e.target)) return;
      drag = { x: e.clientX, y: e.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
      viewport.classList.add("is-dragging");
      e.preventDefault();
      viewport.focus({ preventScroll: true });
    });
    window.addEventListener("mousemove", function (e) {
      if (!drag) return;
      if (!(e.buttons & 1)) { endDrag(); return; } // the button was let go somewhere we did not see
      viewport.scrollLeft = drag.left - (e.clientX - drag.x);
      viewport.scrollTop = drag.top - (e.clientY - drag.y);
    });
    window.addEventListener("mouseup", endDrag);
    window.addEventListener("blur", endDrag);

    // ---- controls ----
    viewport.tabIndex = 0;
    viewport.setAttribute("role", "group");
    viewport.setAttribute("aria-label", "Handbook pages. Left and right arrow keys turn the page; when zoomed in, the arrow keys move around the page.");

    function arrow(btn, action) {
      btn.addEventListener("click", function () {
        if (btn.getAttribute("aria-disabled") !== "true") action();
      });
    }
    arrow(prevBtn, prev);
    arrow(nextBtn, next);

    if (slider) slider.addEventListener("input", function () { go(parseInt(slider.value, 10) || 1, false); });
    if (toc) toc.addEventListener("change", function () { go(parseInt(toc.value, 10), false); });

    // Links inside the book that point at another page.
    book.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest('a[href^="#p"]');
      var m = a && /^#p(\d+)$/.exec(a.getAttribute("href"));
      if (!m) return;
      e.preventDefault();
      go(parseInt(m[1], 10), false);
      viewport.focus({ preventScroll: true }); // the link that was clicked is no longer on screen
    });
    window.addEventListener("hashchange", function () {
      var n = fromHash();
      if (n) go(n, false);
    });

    // Keys apply only when focus is on the book or its arrows, or nowhere in
    // particular, so they never take over form controls or the rest of the page.
    document.addEventListener("keydown", function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      var t = e.target;
      var tag = t.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || t.isContentEditable) return;
      if (t !== document.body && !wrap.contains(t)) return;
      var k = e.key;
      if (zoom && /^Arrow/.test(k)) {
        var dx = viewport.clientWidth * 0.2, dy = viewport.clientHeight * 0.2;
        if (k === "ArrowRight") viewport.scrollLeft += dx;
        else if (k === "ArrowLeft") viewport.scrollLeft -= dx;
        else if (k === "ArrowDown") viewport.scrollTop += dy;
        else viewport.scrollTop -= dy;
      }
      else if (k === "ArrowRight") next();
      else if (k === "ArrowLeft") prev();
      else if (k === "Home" && t === viewport) go(1, false);
      else if (k === "End" && t === viewport) go(total, false);
      else if (k === "+" || k === "=") setZoom(zoom + 1);
      else if (k === "-") setZoom(zoom - 1);
      else if (k === "0") setZoom(0);
      else return;
      e.preventDefault();
    });

    // Swipe left or right on a touch screen.
    var swipe = null;
    book.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse") return;
      // A second finger means a pinch, not a swipe.
      swipe = swipe ? { cancelled: true } : { id: e.pointerId, x: e.clientX, y: e.clientY };
    });
    book.addEventListener("pointerup", function (e) {
      var s = swipe;
      swipe = null;
      if (!s || s.cancelled || s.id !== e.pointerId || zoom) return; // zoomed: a swipe moves around the page
      var dx = e.clientX - s.x, dy = e.clientY - s.y;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) { if (dx < 0) next(); else prev(); }
    });
    book.addEventListener("pointercancel", function () { swipe = null; });

    if (fullBtn) {
      if (main && main.requestFullscreen && document.fullscreenEnabled) {
        fullBtn.addEventListener("click", function () {
          var done = document.fullscreenElement ? document.exitFullscreen() : main.requestFullscreen();
          if (done && done.catch) done.catch(function () {});
        });
        document.addEventListener("fullscreenchange", function () {
          fullBtn.textContent = document.fullscreenElement ? "Exit full screen" : "Full screen";
        });
      } else {
        fullBtn.hidden = true; // iPhones cannot put part of a page full screen
      }
    }

    function onModeChange() {
      if (finishTurn) finishTurn();
      single = singleQuery.matches;
      root.classList.toggle("is-single", single);
      render();
    }
    if (singleQuery.addEventListener) singleQuery.addEventListener("change", onModeChange);
    else singleQuery.addListener(onModeChange);

    current = fromHash() || 1;
    render();
  }
})();
