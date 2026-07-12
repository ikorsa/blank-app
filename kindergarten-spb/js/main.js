(() => {
  const header = document.querySelector(".site-header");
  const form = document.querySelector(".visit-form");
  const note = document.querySelector(".form-note");

  const onScroll = () => {
    if (!header) return;
    header.classList.toggle("is-scrolled", window.scrollY > 24);
  };

  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  if (form && note) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      note.textContent = "Спасибо! В демо заявка сохранена только в браузере.";
      note.classList.add("is-success");
      form.reset();
    });
  }
})();
