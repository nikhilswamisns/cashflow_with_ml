// Navigation drawer (narrow screens) and the top-bar three-dots menu.
(function () {
  const body = document.body;
  const $ = (id) => document.getElementById(id);

  function setNav(open) {
    body.classList.toggle("nav-open", open);
    const b = $("nav-toggle");
    if (b) b.setAttribute("aria-expanded", String(open));
  }
  function setMore(open) {
    const m = $("more-menu"), b = $("more-btn");
    if (!m || !b) return;
    m.hidden = !open;
    b.setAttribute("aria-expanded", String(open));
  }

  document.addEventListener("click", (e) => {
    if (e.target.closest("#nav-toggle")) { setMore(false); return setNav(!body.classList.contains("nav-open")); }
    if (e.target.closest("#nav-backdrop")) return setNav(false);
    if (e.target.closest(".sidebar .nav-btn")) setNav(false);
    if (e.target.closest("#more-btn")) return setMore($("more-menu").hidden);
    // keep the menu open while using the date picker, close it for everything else (Sync, Export, Logout...)
    if (e.target.closest("#more-menu")) {
      if (e.target.closest("button")) setMore(false);
    } else setMore(false);
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { setNav(false); setMore(false); } });
  window.addEventListener("resize", () => { if (window.innerWidth > 900) setNav(false); });

  // Not enough room for the date + Sync Zoho in the bar at 1100px and below:
  // move them into the three-dots menu instead of letting the bar wrap.
  const group = document.querySelector(".sync-group"), slot = $("more-sync-slot"), right = document.querySelector(".topbar-right");
  const mq = window.matchMedia("(max-width: 1100px)");
  function place() {
    if (!group || !slot || !right) return;
    if (mq.matches) slot.appendChild(group); else right.insertBefore(group, right.firstChild);
  }
  mq.addEventListener("change", place);
  place();
})();
