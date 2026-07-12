function handleVisit(event) {
  event.preventDefault();
  const note = document.getElementById("form-note");
  if (note) {
    note.hidden = false;
  }
  event.target.reset();
  return false;
}

function initReveal() {
  const nodes = document.querySelectorAll(
    ".about, .day, .groups, .place-copy, .visit-inner"
  );

  nodes.forEach((node) => node.classList.add("reveal"));

  if (!("IntersectionObserver" in window)) {
    nodes.forEach((node) => node.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.16, rootMargin: "0px 0px -8% 0px" }
  );

  nodes.forEach((node) => observer.observe(node));
}

function initHeaderTone() {
  const header = document.querySelector(".site-header");
  const hero = document.querySelector(".hero");
  if (!header || !hero) return;

  const update = () => {
    const pastHero = window.scrollY > hero.offsetHeight - 80;
    header.style.color = pastHero ? "#1c2b24" : "#f7faf8";
    header.style.background = pastHero
      ? "rgba(243, 247, 245, 0.92)"
      : "linear-gradient(180deg, rgba(15, 61, 50, 0.55), transparent)";
    header.style.backdropFilter = pastHero ? "blur(10px)" : "none";
    header.style.boxShadow = pastHero ? "0 1px 0 rgba(28, 43, 36, 0.08)" : "none";
  };

  update();
  window.addEventListener("scroll", update, { passive: true });
}

document.addEventListener("DOMContentLoaded", () => {
  initReveal();
  initHeaderTone();
});
