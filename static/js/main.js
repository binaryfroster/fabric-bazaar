document.addEventListener('DOMContentLoaded', () => {
  // Hamburger menu
  const btn = document.getElementById('hamburgerBtn');
  const nav = document.getElementById('navMenu');
  if (btn && nav) {
    btn.onclick = () => { nav.classList.toggle('open'); };
    document.addEventListener('click', e => {
      if (!nav.contains(e.target) && !btn.contains(e.target)) nav.classList.remove('open');
    });
  }

  // Sticky navbar shadow
  const navbar = document.getElementById('navbar');
  window.addEventListener('scroll', () => {
    if (navbar) navbar.style.boxShadow = window.scrollY > 10 ? '0 4px 20px rgba(0,0,0,.1)' : '';
  });

  // Reveal on scroll
  const observer = new IntersectionObserver(entries => {
    entries.forEach((e, i) => {
      if (e.isIntersecting) {
        setTimeout(() => e.target.classList.add('visible'), i * 60);
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.1 });
  document.querySelectorAll('.reveal-on-scroll').forEach(el => observer.observe(el));

  // Auto-dismiss flash messages
  setTimeout(() => {
    document.querySelectorAll('.flash').forEach(f => f.remove());
  }, 5000);

  // Duplicate ticker content for seamless loop
  const ticker = document.getElementById('ticker');
  if (ticker) ticker.innerHTML += ticker.innerHTML;
});
