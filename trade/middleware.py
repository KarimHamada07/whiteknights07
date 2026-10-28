THEME = r"""
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style id="erp-theme">
/* خط ParisMetro للحروف الإنجليزي فقط. الأرقام والعربي بخطوطهم عشان تفضل مقروءة */
@font-face{font-family:"ParisMetro";src:url("/static/trade/fonts/PARISME_.TTF") format("truetype");
  unicode-range:U+0041-005A,U+0061-007A;font-display:swap}
:root{--erp-red:#d70812;--erp-red-d:#a80610;--erp-black:#0f0f10;--erp-silver:#b4b4b4;--erp-line:#e2e2e4;
  --bs-body-font-family:"ParisMetro","Source Sans 3",Cairo,"Segoe UI",Tahoma,sans-serif;
  --bs-font-sans-serif:"ParisMetro","Source Sans 3",Cairo,"Segoe UI",Tahoma,sans-serif}
[data-bs-theme=light]{--bs-primary:#d70812;--bs-primary-rgb:215,8,18;--bs-link-color:#d70812;
  --bs-link-color-rgb:215,8,18;--bs-link-hover-color:#a80610;--bs-link-hover-color-rgb:168,6,16;
  --bs-body-bg:#fff;--bs-tertiary-bg:#fff;--bs-border-color:#e2e2e4}
html,body,button,input,select,textarea{font-family:var(--bs-body-font-family)}
body{font-synthesis-weight:none}
input[type=checkbox],input[type=radio]{accent-color:var(--erp-red)}

/* القائمة الجانبية: أسود، والنشط أحمر */
#jazzy-sidebar{background-color:var(--erp-black)!important;--lte-sidebar-hover-bg:rgba(255,255,255,.1);
  --lte-sidebar-menu-active-bg:var(--erp-red);--lte-sidebar-menu-active-color:#fff}
#jazzy-sidebar .nav-link.active{background-color:var(--erp-red)!important;color:#fff!important}
#jazzy-sidebar .sidebar-brand{background:var(--erp-black);border-bottom:1px solid #2a2a2c}
#jazzy-sidebar .brand-image{opacity:1!important;max-height:44px;width:44px;object-fit:contain}
.app-header{background:#fff!important;border-bottom:1px solid var(--erp-line)!important}
.app-header .nav-link{color:var(--erp-black)}

/* كروت وجداول */
.card{border:1px solid var(--erp-line);box-shadow:none;border-radius:12px}
.card-header{background:#fff}
.card-outline.card-primary,.card-outline.card-warning,.card-outline.card-success{border-top:3px solid var(--erp-red)}
.form-control:focus,.form-select:focus{border-color:var(--erp-red);box-shadow:0 0 0 .2rem rgba(215,8,18,.15)}

/* أزرار */
.btn-primary,.btn-danger{--bs-btn-bg:var(--erp-red);--bs-btn-border-color:var(--erp-red);--bs-btn-color:#fff;
  --bs-btn-hover-bg:var(--erp-red-d);--bs-btn-hover-border-color:var(--erp-red-d);--bs-btn-hover-color:#fff;
  --bs-btn-active-bg:var(--erp-red-d);--bs-btn-active-border-color:var(--erp-red-d);--bs-btn-active-color:#fff;
  --bs-btn-disabled-bg:var(--erp-red);--bs-btn-disabled-border-color:var(--erp-red)}
.btn-success,.btn-dark{--bs-btn-bg:var(--erp-black);--bs-btn-border-color:var(--erp-black);--bs-btn-color:#fff;
  --bs-btn-hover-bg:#2a2a2c;--bs-btn-hover-border-color:#2a2a2c;--bs-btn-hover-color:#fff;
  --bs-btn-active-bg:#2a2a2c;--bs-btn-active-border-color:#2a2a2c;--bs-btn-active-color:#fff;
  --bs-btn-disabled-bg:var(--erp-black);--bs-btn-disabled-border-color:var(--erp-black)}
.btn-info,.btn-warning{--bs-btn-bg:#fff;--bs-btn-border-color:var(--erp-black);--bs-btn-color:var(--erp-black);
  --bs-btn-hover-bg:var(--erp-black);--bs-btn-hover-border-color:var(--erp-black);--bs-btn-hover-color:#fff;
  --bs-btn-active-bg:var(--erp-black);--bs-btn-active-border-color:var(--erp-black);--bs-btn-active-color:#fff}
.btn-outline-primary{--bs-btn-color:var(--erp-red);--bs-btn-border-color:var(--erp-red);
  --bs-btn-hover-bg:var(--erp-red);--bs-btn-hover-border-color:var(--erp-red);--bs-btn-hover-color:#fff;
  --bs-btn-active-bg:var(--erp-red);--bs-btn-active-border-color:var(--erp-red);--bs-btn-active-color:#fff}

/* توافق مع أسماء Bootstrap 4 المستخدمة في الصفحات (غير موجودة في القالب) */
.badge-primary,.badge-dark{background:var(--erp-black);color:#fff}
.badge-secondary,.badge-info{background:var(--erp-silver);color:#111}
.badge-success{background:#fff;color:#111;border:1px solid var(--erp-black)}
.badge-warning{background:#fff;color:var(--erp-red);border:1px solid var(--erp-red)}
.badge-danger{background:var(--erp-red);color:#fff}
.btn-block{display:block;width:100%}
.text-right{text-align:right!important}
.text-left{text-align:left!important}

/* الموبايل: القائمة مقفولة افتراضياً وبتفتح بزر، وعرضها 80% بحد أقصى 300px */
.erp-sidebar-close{display:none;width:100%;padding:14px;border:0;background:var(--erp-red);color:#fff;font-weight:700;font-size:16px}
@media (max-width:991.98px){
  #jazzy-sidebar{--lte-sidebar-width:min(80vw,300px)}
  .erp-sidebar-close{display:block}
  .app-header [data-lte-toggle=sidebar]{font-size:22px;padding:10px 14px}
}
</style>
<script id="erp-theme-js">
(function () {
  function mobile() { return window.innerWidth < 992; }
  function closeSb() { document.body.classList.remove("sidebar-open"); }
  // القالب بيكتب sidebar-open ثابت في الصفحة، فالقايمة كانت بتبدأ مفتوحة على الموبايل
  if (mobile()) closeSb();
  var sb = document.getElementById("jazzy-sidebar");
  if (sb && !sb.querySelector(".erp-sidebar-close")) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "erp-sidebar-close";
    b.textContent = "\u2715 \u0625\u063a\u0644\u0627\u0642 \u0627\u0644\u0642\u0627\u0626\u0645\u0629";
    b.addEventListener("click", closeSb);
    sb.insertBefore(b, sb.firstChild);
    sb.addEventListener("click", function (e) {
      var a = e.target.closest("a.nav-link"), h = a && a.getAttribute("href");
      if (mobile() && h && h !== "#" && h.indexOf("javascript") !== 0) closeSb();
    });
  }
  window.addEventListener("load", function () { if (mobile()) closeSb(); });
})();
</script>
"""


class MobileSidebarMiddleware:
    """يحقن ثيم النظام (ألوان الشعار + خط ParisMetro + إصلاح القايمة على الموبايل)
    في كل صفحات لوحة الإدارة والصفحات المبنية عليها."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.snippet = THEME.encode("utf-8")

    def __call__(self, request):
        response = self.get_response(request)
        if (
            "text/html" in response.get("Content-Type", "")
            and not response.streaming
            and response.status_code == 200
            and b"</body>" in response.content
            and b"vendor/adminlte/css/adminlte" in response.content   # صفحات القالب فقط
        ):
            response.content = response.content.replace(
                b"</body>", self.snippet + b"</body>", 1)
            if response.has_header("Content-Length"):
                response["Content-Length"] = str(len(response.content))
        return response
