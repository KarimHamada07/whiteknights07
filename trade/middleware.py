SNIPPET = """
<style id="mobile-sidebar-style">
#sidebar-close, #mobile-backdrop { display: none; }
@media (max-width: 991.98px) {
  #sidebar-overlay { display: none !important; }
  #mobile-backdrop {
    position: fixed; top: 0; right: 0; bottom: 0; left: 0;
    background: rgba(0, 0, 0, .5); z-index: 1040;
  }
  body.mobile-menu-open #mobile-backdrop { display: block; }
  #sidebar-close {
    display: block !important;
    width: 100%;
    padding: 14px;
    border: 0;
    background: #c53030;
    color: #fff;
    font-size: 16px;
    font-weight: 700;
  }
  .navbar-nav [data-widget="pushmenu"] {
    font-size: 26px !important;
    padding: 8px 16px !important;
  }
  .content-wrapper, .main-footer, .main-header, .app-main, .app-header {
    margin-left: 0 !important;
    margin-right: 0 !important;
  }
}
</style>
<script id="mobile-sidebar-script">
(function () {
  var sidebarEl = null;

  function isMobile() { return window.innerWidth < 992; }

  // يدور على القائمة الظاهرة فعلاً: العنصر الثابت الموجود عند حافة الشاشة
  function findSidebar() {
    if (sidebarEl && document.body.contains(sidebarEl)) return sidebarEl;
    var w = window.innerWidth, y = Math.round(window.innerHeight * 0.5);
    var xs = [w - 20, 20];
    for (var i = 0; i < xs.length; i++) {
      var el = document.elementFromPoint(xs[i], y);
      while (el && el !== document.body && el !== document.documentElement) {
        var cs = getComputedStyle(el);
        if ((cs.position === "fixed" || cs.position === "absolute") &&
            el.offsetWidth < w * 0.9 && el.offsetHeight > window.innerHeight * 0.5) {
          sidebarEl = el;
          return el;
        }
        el = el.parentElement;
      }
    }
    var fallback = document.querySelector(".main-sidebar, .app-sidebar, aside");
    if (fallback) sidebarEl = fallback;
    return fallback;
  }

  function setOpen(open) {
    document.body.classList.toggle("mobile-menu-open", open);
    var el = findSidebar();
    if (!el) return;
    if (open) {
      el.style.removeProperty("display");
      el.style.setProperty("z-index", "1050", "important");
      el.style.setProperty("width", "80vw", "important");
      el.style.setProperty("max-width", "300px", "important");
      if (getComputedStyle(el).display === "none") {
        el.style.setProperty("display", "block", "important");
      }
    } else {
      el.style.setProperty("display", "none", "important");
    }
  }

  function toggleTarget(e) {
    var t = e.target.closest('[data-widget="pushmenu"],[data-lte-toggle="sidebar"],[data-bs-toggle="offcanvas"],.navbar-toggler');
    if (t) return t;
    var a = e.target.closest("a,button");
    if (a && a.querySelector(".fa-bars, .fa-align-justify, .fa-bars-staggered")) return a;
    return null;
  }

  document.addEventListener("click", function (e) {
    if (!isMobile()) return;
    if (toggleTarget(e)) {
      e.preventDefault();
      e.stopImmediatePropagation();
      setOpen(!document.body.classList.contains("mobile-menu-open"));
    }
  }, true);

  function init() {
    if (!isMobile()) return;
    var el = findSidebar();
    if (!document.getElementById("mobile-backdrop")) {
      var backdrop = document.createElement("div");
      backdrop.id = "mobile-backdrop";
      backdrop.addEventListener("click", function () { setOpen(false); });
      document.body.appendChild(backdrop);
    }
    if (el && !document.getElementById("sidebar-close")) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.id = "sidebar-close";
      btn.textContent = "\\u2715 \\u0625\\u063a\\u0644\\u0627\\u0642 \\u0627\\u0644\\u0642\\u0627\\u0626\\u0645\\u0629";
      btn.addEventListener("click", function () { setOpen(false); });
      el.insertBefore(btn, el.firstChild);
      el.addEventListener("click", function (e) {
        var link = e.target.closest("a");
        var href = link && link.getAttribute("href");
        if (href && href !== "#" && href.indexOf("javascript") !== 0) setOpen(false);
      });
    }
    if (!document.body.classList.contains("mobile-menu-open")) setOpen(false);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  window.addEventListener("load", function () {
    setTimeout(init, 300);
    setTimeout(init, 1200);
  });

  // ---- شريط التشخيص المؤقت ----
  var d = document.createElement("div");
  d.style.cssText = "position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#000;color:#0f0;font:12px monospace;padding:4px 6px;direction:ltr;text-align:left";
  function info() {
    var f = sidebarEl;
    var desc = f ? (f.tagName + (f.id ? "#" + f.id : "") + "." + String(f.className).split(" ").slice(0, 2).join(".")) : "null";
    d.textContent = "v5 w=" + window.innerWidth + " found=" + desc + " disp=" + (f ? getComputedStyle(f).display : "-");
  }
  window.addEventListener("load", function () {
    document.body.appendChild(d); info(); setInterval(info, 1000);
  });
})();
</script>
"""


class MobileSidebarMiddleware:
    """يحقن ستايل وسكريبت القائمة الجانبية للموبايل في كل صفحة HTML."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.snippet = SNIPPET.encode("utf-8")

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get("Content-Type", "")
        if (
            "text/html" in content_type
            and not response.streaming
            and response.status_code == 200
            and b"</body>" in response.content
        ):
            response.content = response.content.replace(
                b"</body>", self.snippet + b"</body>", 1
            )
            if response.has_header("Content-Length"):
                response["Content-Length"] = str(len(response.content))
        return response
