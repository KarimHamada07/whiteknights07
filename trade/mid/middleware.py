SNIPPET = """
<style id="mobile-sidebar-style">
#sidebar-close { display: none; }
@media (max-width: 991.98px) {
  .main-sidebar, .main-sidebar::before {
    width: 80vw !important;
    max-width: 300px !important;
  }
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
  .main-sidebar .nav-link { padding: 12px 14px; font-size: 16px; }
}
</style>
<script id="mobile-sidebar-script">
(function () {
  function isMobile() { return window.innerWidth < 992; }
  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    document.body.classList.add("sidebar-collapse");
  }
  function setup() {
    if (!isMobile()) return;
    closeSidebar();
    var sidebar = document.querySelector(".main-sidebar");
    if (!sidebar || document.getElementById("sidebar-close")) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.id = "sidebar-close";
    btn.textContent = "\\u2715 \\u0625\\u063a\\u0644\\u0627\\u0642 \\u0627\\u0644\\u0642\\u0627\\u0626\\u0645\\u0629";
    btn.addEventListener("click", closeSidebar);
    sidebar.insertBefore(btn, sidebar.firstChild);
    sidebar.addEventListener("click", function (e) {
      var link = e.target.closest("a.nav-link");
      var href = link && link.getAttribute("href");
      if (href && href !== "#" && href.indexOf("javascript") !== 0) closeSidebar();
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup);
  } else {
    setup();
  }
  window.addEventListener("load", function () {
    if (isMobile()) setTimeout(closeSidebar, 200);
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
