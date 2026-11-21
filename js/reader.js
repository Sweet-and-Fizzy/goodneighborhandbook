/* The online handbook reader. Without this script the pages on /read/ simply
   stack and scroll; with it they become a book you page through. */
(function () {
  "use strict";

  var root = document.documentElement;
  var singleQuery = window.matchMedia("(max-width: 56rem) and (orientation: portrait), (max-width: 40rem)");
  // Set these straight away, before the page is drawn, so the stacked pages never flash.
  root.classList.add("js-reader");
  root.classList.toggle("is-single", singleQuery.matches);

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();

  function start() {
  var book = document.getElementById("book");
  if (!book) return;

  var pages = Array.prototype.slice.call(book.querySelectorAll(".page"));
  var total = pages.length;
  var main = document.getElementById("main");
  var controls = document.getElementById("reader-controls");
  var prevBtn = document.getElementById("reader-prev");
  var nextBtn = document.getElementById("reader-next");
  var slider = document.getElementById("reader-slider");
  var status = document.getElementById("reader-status");
  var toc = document.getElementById("reader-toc");
  var fullBtn = document.getElementById("reader-full");

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var single = singleQuery.matches;
  var current = 1; // the page being read (in a spread, either page of it)
  var turning = false;

  function clamp(n) { return Math.min(total, Math.max(1, n)); }

  // Page 1 sits alone on the right; after that even pages are on the left.
  function spreadOf(n) {
    var left = n % 2 === 0 ? n : n - 1;
    return { left: left >= 1 ? left : null, right: left + 1 <= total ? left + 1 : null };
  }
  function page(n) { return n ? pages[n - 1] : null; }
  function image(n) { return page(n).querySelector("img"); }

  // Images are lazy; fetch the ones a page turn away so turns are not blank.
  function preload(n) {
    for (var i = clamp(n - 4); i <= clamp(n + 5); i++) image(i).loading = "eager";
  }

  function render() {
    var s = spreadOf(current);
    pages.forEach(function (p) { p.classList.remove("is-left", "is-right", "is-current"); });
    if (single) {
      page(current).classList.add("is-current");
    } else {
      if (s.left) page(s.left).classList.add("is-left");
      if (s.right) page(s.right).classList.add("is-right");
    }
    var first = single ? current : (s.left || s.right);
    var last = single ? current : (s.right || s.left);
    status.textContent = (first === last ? "Page " + first : "Pages " + first + "–" + last) + " of " + total;
    slider.value = current;
    prevBtn.disabled = first <= 1;
    nextBtn.disabled = last >= total;
    preload(current);
    if (window.history && history.replaceState) history.replaceState(null, "", "#p" + first);
  }

  function face(n, cls) {
    var el = document.createElement("div");
    el.className = "leaf__face " + cls;
    if (n) {
      var img = image(n).cloneNode(false);
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

    turning = true;
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

    var done = false;
    function finish() {
      if (done) return;
      done = true;
      current = target;
      render();
      leaf.remove();
      turning = false;
    }
    leaf.addEventListener("transitionend", finish);
    window.setTimeout(finish, 900);
  }

  function go(n, animate) {
    n = clamp(n);
    if (turning || isNaN(n)) return;
    var from = spreadOf(current);
    var to = spreadOf(n);
    var sameView = single ? n === current : from.left === to.left;
    if (sameView) { current = n; render(); return; }
    var adjacent = Math.abs((to.left || 0) - (from.left || 0)) === 2;
    if (animate && adjacent && !single && !reduceMotion.matches) {
      turn(from, to, n);
    } else {
      current = n;
      render();
    }
  }

  function next() {
    var s = spreadOf(current);
    go(single ? current + 1 : (s.right || s.left) + 1, true);
  }
  function prev() {
    var s = spreadOf(current);
    go(single ? current - 1 : (s.left || s.right) - 1, true);
  }

  function fromHash() {
    var m = /^#p(\d+)$/.exec(window.location.hash);
    return m ? clamp(parseInt(m[1], 10)) : null;
  }

  // ---- wire everything up ----
  controls.hidden = false;
  prevBtn.hidden = false;
  nextBtn.hidden = false;

  prevBtn.addEventListener("click", prev);
  nextBtn.addEventListener("click", next);
  slider.addEventListener("input", function () { go(parseInt(slider.value, 10), false); });
  toc.addEventListener("change", function () {
    if (toc.value) go(parseInt(toc.value, 10), false);
    toc.value = "";
  });
  window.addEventListener("hashchange", function () {
    var n = fromHash();
    if (n) go(n, false);
  });

  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    var tag = e.target.tagName;
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { next(); e.preventDefault(); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { prev(); e.preventDefault(); }
    else if (e.key === "Home") { go(1, false); e.preventDefault(); }
    else if (e.key === "End") { go(total, false); e.preventDefault(); }
  });

  // Swipe left or right on a touch screen.
  var startX = null, startY = null;
  book.addEventListener("pointerdown", function (e) {
    if (e.pointerType === "mouse") return;
    startX = e.clientX; startY = e.clientY;
  });
  book.addEventListener("pointerup", function (e) {
    if (startX === null) return;
    var dx = e.clientX - startX, dy = e.clientY - startY;
    startX = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) { if (dx < 0) next(); else prev(); }
  });
  book.addEventListener("pointercancel", function () { startX = null; });

  if (main.requestFullscreen && document.fullscreenEnabled) {
    fullBtn.addEventListener("click", function () {
      if (document.fullscreenElement) document.exitFullscreen();
      else main.requestFullscreen();
    });
    document.addEventListener("fullscreenchange", function () {
      fullBtn.textContent = document.fullscreenElement ? "Exit full screen" : "Full screen";
    });
  } else {
    fullBtn.hidden = true;
  }

  function onModeChange() {
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
