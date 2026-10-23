(function () {
  function isMobile() {
    return window.innerWidth < 992;
  }

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    document.body.classList.add("sidebar-collapse");
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!isMobile()) return;

    // القائمة مقفولة افتراضياً على الموبايل
    closeSidebar();

    var sidebar = document.querySelector(".main-sidebar");
    if (!sidebar) return;

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
      if (link && link.getAttribute("href") && link.getAttribute("href") !== "#") {
        closeSidebar();
      }
    });
  });
})();
