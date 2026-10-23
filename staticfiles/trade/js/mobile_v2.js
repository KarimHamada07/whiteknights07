(function () {
  function isMobile() {
    return window.innerWidth < 992;
  }

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    document.body.classList.add("sidebar-collapse");
  }

  function setup() {
    if (!isMobile()) return;
    closeSidebar();

    var sidebar = document.querySelector(".main-sidebar");
    if (!sidebar || document.getElementById("sidebar-close")) return;

    // زر إغلاق أعلى القائمة
    var btn = document.createElement("button");
    btn.type = "button";
    btn.id = "sidebar-close";
    btn.textContent = "✕ إغلاق القائمة";
    btn.addEventListener("click", closeSidebar);
    sidebar.insertBefore(btn, sidebar.firstChild);

    // قفل القائمة تلقائياً بعد اختيار صفحة
    sidebar.addEventListener("click", function (e) {
      var link = e.target.closest("a.nav-link");
      var href = link && link.getAttribute("href");
      if (href && href !== "#" && href.indexOf("javascript") !== 0) {
        closeSidebar();
      }
    });
  }

  // يشتغل سواء الصفحة لسه بتتحمل أو خلصت
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup);
  } else {
    setup();
  }

  // تأكيد القفل بعد ما قالب Jazzmin يخلّص تجهيزه
  window.addEventListener("load", function () {
    if (isMobile()) setTimeout(closeSidebar, 200);
  });
})();
