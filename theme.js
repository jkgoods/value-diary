// Immediately apply saved theme before DOM mounts to prevent flash
(function () {
  let savedTheme = 'dark';
  try {
    savedTheme = localStorage.getItem('theme') || 'dark';
  } catch (e) {
    console.warn('localStorage read blocked, defaulting to dark:', e);
  }
  document.documentElement.setAttribute('data-theme', savedTheme);
})();

document.addEventListener('DOMContentLoaded', () => {
  // 1. Inject Menu Icons
  const portfolioLink = document.querySelector('.nav-links a[href*="portfolio.html"]');
  if (portfolioLink && !portfolioLink.querySelector('.nav-icon')) {
    portfolioLink.insertAdjacentHTML('afterbegin', `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/></svg>`);
  }

  const diaryLink = document.querySelector('.nav-links a[href*="diary.html"]');
  if (diaryLink && !diaryLink.querySelector('.nav-icon')) {
    diaryLink.insertAdjacentHTML('afterbegin', `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M6 6h10M6 10h10"/></svg>`);
  }

  const aboutLink = document.querySelector('.nav-links a[href*="about.html"]');
  if (aboutLink && !aboutLink.querySelector('.nav-icon')) {
    aboutLink.insertAdjacentHTML('afterbegin', `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`);
  }

  // 2. Inject Diary Tag Emojis
  const injectEmojis = (selector) => {
    document.querySelectorAll(selector).forEach(el => {
      const text = el.textContent.trim();
      if (el.dataset.emojiApplied) return;
      if (text.includes('스크리닝')) { el.prepend('🔍 '); el.dataset.emojiApplied = 'true'; }
      else if (text.includes('소개'))  { el.prepend('📣 '); el.dataset.emojiApplied = 'true'; }
      else if (text.includes('심리'))  { el.prepend('💭 '); el.dataset.emojiApplied = 'true'; }
      else if (text.includes('결과'))  { el.prepend('📊 '); el.dataset.emojiApplied = 'true'; }
    });
  };
  injectEmojis('.diary-type');
  injectEmojis('.article-type');

  // 3. Inject Theme Toggle Button
  const navLinks = document.querySelector('.nav-links');
  if (!navLinks) return;

  const SUN_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>`;
  const MOON_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;

  const toggleBtn = document.createElement('button');
  toggleBtn.className = 'theme-toggle-btn';
  toggleBtn.setAttribute('aria-label', '테마 변경');

  const currentTheme = document.documentElement.getAttribute('data-theme');
  toggleBtn.innerHTML = currentTheme === 'dark' ? SUN_ICON : MOON_ICON;

  toggleBtn.addEventListener('click', () => {
    const active = document.documentElement.getAttribute('data-theme');
    const next = active === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('theme', next); } catch (e) {}
    toggleBtn.innerHTML = next === 'dark' ? SUN_ICON : MOON_ICON;
  });

  navLinks.appendChild(toggleBtn);
});
