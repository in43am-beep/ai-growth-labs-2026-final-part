// AI SEO Agency - Main JavaScript

document.addEventListener('DOMContentLoaded', () => {

  // Header scroll effect
  const header = document.querySelector('.header');
  if (header) {
    window.addEventListener('scroll', () => {
      header.classList.toggle('scrolled', window.scrollY > 50);
    });
  }

  // Mobile nav toggle
  const navToggle = document.querySelector('.nav-toggle');
  const navLinks = document.querySelector('.nav-links');
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      navLinks.classList.toggle('active');
    });
  }

  // Mobile dropdown toggle
  document.querySelectorAll('.nav-dropdown > a').forEach(link => {
    link.addEventListener('click', (e) => {
      if (window.innerWidth <= 768) {
        e.preventDefault();
        link.parentElement.classList.toggle('active');
      }
    });
  });

  // FAQ accordion
  document.querySelectorAll('.faq-question').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.parentElement;
      const isActive = item.classList.contains('active');
      document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('active'));
      if (!isActive) item.classList.add('active');
    });
  });

  // Animate on scroll
  const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, observerOptions);

  document.querySelectorAll('.service-card, .case-card, .testimonial-card, .pricing-card, .industry-card, .blog-card, .feature-item').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
  });

  // Counter animation
  let countersAnimated = false;
  function animateCounters() {
    if (countersAnimated) return;
    countersAnimated = true;
    document.querySelectorAll('[data-count]').forEach(counter => {
      const target = parseInt(counter.dataset.count);
      const suffix = counter.dataset.suffix || '';
      const prefix = counter.dataset.prefix || '';
      const duration = 2000;
      const start = 0;
      const step = (target - start) / (duration / 16);
      let current = start;

      const update = () => {
        current += step;
        if (current < target) {
          counter.textContent = prefix + Math.floor(current).toLocaleString() + suffix;
          requestAnimationFrame(update);
        } else {
          counter.textContent = prefix + target.toLocaleString() + suffix;
        }
      };
      update();
    });
  }

  const counterSection = document.querySelector('.hero-stats');
  if (counterSection) {
    const rect = counterSection.getBoundingClientRect();
    if (rect.top < window.innerHeight && rect.bottom > 0) {
      setTimeout(animateCounters, 300);
    }
    const counterObserver = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        animateCounters();
        counterObserver.disconnect();
      }
    }, { threshold: 0.1 });
    counterObserver.observe(counterSection);
    // Fallback: ensure counters animate after 3 seconds if still not triggered
    setTimeout(() => { animateCounters(); }, 3000);
    // Also trigger on scroll
    window.addEventListener('scroll', function scrollCheck() {
      const r = counterSection.getBoundingClientRect();
      if (r.top < window.innerHeight && r.bottom > 0) {
        animateCounters();
        window.removeEventListener('scroll', scrollCheck);
      }
    });
  }

  // Form validation (skip forms with custom onsubmit handlers)
  document.querySelectorAll('form').forEach(form => {
    if (form.getAttribute('onsubmit')) return;
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const btn = form.querySelector('.btn');
      if (btn) {
        const original = btn.textContent;
        btn.textContent = 'Thank You! We\'ll Contact You Soon.';
        btn.style.background = '#00C853';
        setTimeout(() => {
          btn.textContent = original;
          btn.style.background = '';
          form.reset();
        }, 3000);
      }
    });
  });

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const id = this.getAttribute('href');
      if (id === '#') return;
      e.preventDefault();
      const el = document.querySelector(id);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (navLinks) navLinks.classList.remove('active');
      }
    });
  });

  // Sticky CTA bar - show after scrolling past hero
  const stickyCTA = document.getElementById('stickyCTA');
  if (stickyCTA) {
    let ctaDismissed = false;
    window.addEventListener('scroll', () => {
      if (ctaDismissed) return;
      if (window.scrollY > 600) {
        stickyCTA.classList.add('visible');
      } else {
        stickyCTA.classList.remove('visible');
      }
    });
    const closeBtn = stickyCTA.querySelector('.sticky-cta-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        ctaDismissed = true;
        stickyCTA.classList.remove('visible');
      });
    }
  }

  // Mobile mega-menu sidebar
  if (navToggle && navLinks) {
    // Close mega menu when clicking outside
    document.addEventListener('click', (e) => {
      if (window.innerWidth <= 768 && navLinks.classList.contains('active')) {
        if (!navLinks.contains(e.target) && !navToggle.contains(e.target)) {
          navLinks.classList.remove('active');
        }
      }
    });
  }

  // Lazy load images below fold
  if ('IntersectionObserver' in window) {
    const imgObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          if (img.dataset.src) {
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
          }
          imgObserver.unobserve(img);
        }
      });
    }, { rootMargin: '200px' });

    document.querySelectorAll('img[data-src]').forEach(img => {
      imgObserver.observe(img);
    });
  }

  // WhatsApp floating button removed — now handled by fab-container in HTML

  // Results ticker: clone items once for a seamless marquee loop (no duplicate markup in HTML source)
  var tickerInner = document.querySelector('.ticker-inner');
  if (tickerInner && !tickerInner.dataset.cloned) {
    tickerInner.innerHTML += tickerInner.innerHTML;
    tickerInner.dataset.cloned = '1';
  }
});
