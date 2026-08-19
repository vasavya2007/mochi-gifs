/**
 * tiny.gif — Client Application Logic ♡
 * Handles collection loading, live search, tag filtering, modal inspection,
 * carousel navigation, favorites management, copy helpers, and canvas particles.
 */

(function () {
  'use strict';

  // --- LocalStorage Favorites Helper ---
  const FAVORITES_KEY = 'tiny_gif_favorites';
  function getFavorites() {
    try {
      return JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]');
    } catch {
      return [];
    }
  }
  function saveFavorites(favs) {
    try {
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(favs));
    } catch {}
  }
  function isFavorite(gifId) {
    return getFavorites().includes(gifId);
  }
  function toggleFavorite(gifId) {
    let favs = getFavorites();
    if (favs.includes(gifId)) {
      favs = favs.filter(id => id !== gifId);
    } else {
      favs.push(gifId);
    }
    saveFavorites(favs);
    return favs.includes(gifId);
  }

  // --- Theme Management ---
  const THEMES = [
    { id: 'strawberry', icon: '🌸', name: 'Strawberry Milk' },
    { id: 'lavender', icon: '🌙', name: 'Lavender Dream' },
    { id: 'matcha', icon: '🍵', name: 'Matcha Mint' },
    { id: 'honey', icon: '🍯', name: 'Honey Butter' }
  ];
  const THEME_KEY = 'tiny_gif_theme';
  function getSavedTheme() {
    return localStorage.getItem(THEME_KEY) || 'strawberry';
  }
  function applyTheme(themeId, notify = false) {
    const theme = THEMES.find(t => t.id === themeId) || THEMES[0];
    document.documentElement.setAttribute('data-theme', theme.id);
    localStorage.setItem(THEME_KEY, theme.id);
    const themeIconEl = document.getElementById('theme-icon');
    if (themeIconEl) themeIconEl.textContent = theme.icon;
    if (notify) showToast(`theme: ${theme.name} ${theme.icon}`);
  }
  function cycleTheme() {
    const current = getSavedTheme();
    const idx = THEMES.findIndex(t => t.id === current);
    const nextTheme = THEMES[(idx + 1) % THEMES.length];
    applyTheme(nextTheme.id, true);
  }

  // --- Application State ---
  const state = {
    allGifs: [],
    filteredGifs: [],
    tags: [],
    activeTag: 'all',
    searchQuery: '',
    sortBy: 'newest',
    selectedGif: null,
    selectedGifIndex: -1,
    isLoading: true
  };

  // --- Tag Icons Mapping ---
  const TAG_ICONS = {
    all: '✦',
    favorites: '💖',
    cute: '♡',
    miffy: '🐰',
    crying: '💧',
    sleepy: '🌙',
    anime: '🌸',
    cat: '🐾',
    happy: '✨',
    angry: '💢',
    silly: '🎀',
    blush: '😳',
    gojo: '⚡',
    'hello kitty': '🐱',
    strawberry: '🍓',
    reactions: '💬',
    animals: '🐻',
    characters: '🧸'
  };

  function getTagIcon(tagName) {
    const clean = tagName.toLowerCase().trim();
    return TAG_ICONS[clean] || '🏷️';
  }

  // --- DOM Elements ---
  const el = {
    gifGrid: document.getElementById('gif-grid'),
    emptyState: document.getElementById('empty-state'),
    categoryPills: document.getElementById('category-pills'),
    categoriesGrid: document.getElementById('categories-grid'),
    searchInput: document.getElementById('search-input'),
    searchClearBtn: document.getElementById('search-clear-btn'),
    sortSelect: document.getElementById('sort-select'),
    surpriseBtn: document.getElementById('surprise-btn'),
    resultsCount: document.getElementById('results-count'),
    resetSearchBtn: document.getElementById('reset-search-btn'),
    countGifs: document.getElementById('count-gifs'),
    countTags: document.getElementById('count-tags'),
    
    // Modal
    modal: document.getElementById('gif-modal'),
    modalCloseBtn: document.getElementById('modal-close-btn'),
    modalPrevBtn: document.getElementById('modal-prev-btn'),
    modalNextBtn: document.getElementById('modal-next-btn'),
    modalFavBtn: document.getElementById('modal-fav-btn'),
    modalImg: document.getElementById('modal-img'),
    modalTitle: document.getElementById('modal-title'),
    modalTags: document.getElementById('modal-tags'),
    modalDims: document.getElementById('modal-dims'),
    modalDimBadge: document.getElementById('modal-dim-badge'),
    modalSize: document.getElementById('modal-size'),
    modalId: document.getElementById('modal-id'),
    modalSource: document.getElementById('modal-source'),
    modalSourceRow: document.getElementById('modal-source-row'),
    modalUrlInput: document.getElementById('modal-url-input'),
    modalCopyUrlBtn: document.getElementById('modal-copy-url-btn'),
    modalMainCopyBtn: document.getElementById('modal-main-copy-btn'),
    modalDownloadBtn: document.getElementById('modal-download-btn'),
    copyMarkdownBtn: document.getElementById('copy-markdown-btn'),
    copyHtmlBtn: document.getElementById('copy-html-btn'),
    copyDiscordBtn: document.getElementById('copy-discord-btn'),
    
    // Theme Switcher
    themeBtn: document.getElementById('theme-btn'),

    // Toast
    toast: document.getElementById('toast'),
    toastText: document.getElementById('toast-text'),
    
    // Canvas
    bgCanvas: document.getElementById('bg-canvas')
  };

  // --- Initialize App ---
  async function init() {
    applyTheme(getSavedTheme(), false);
    initCanvasParticles();
    setupEventListeners();
    await loadInitialData();
    handleHashNavigation();
  }

  // --- Fetch API Data ---
  async function loadInitialData() {
    try {
      const [colRes, tagsRes] = await Promise.all([
        fetch('/api/collection'),
        fetch('/api/tags')
      ]);

      const colData = await colRes.json();
      const tagsData = await tagsRes.json();

      if (colData.success && Array.isArray(colData.gifs)) {
        state.allGifs = colData.gifs;
      }
      if (tagsData.success && Array.isArray(tagsData.tags)) {
        state.tags = tagsData.tags;
      }

      // Update stat counters
      if (el.countGifs) el.countGifs.textContent = state.allGifs.length;
      if (el.countTags) el.countTags.textContent = Math.max(0, state.tags.length - 1);

      renderCategoryPills();
      renderCategoryDrawer();
      applyFilterAndRender();
    } catch (err) {
      console.error('Error loading tiny.gif collection:', err);
      el.gifGrid.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">(｡•́︿•̀｡)</div>
          <h3>could not load collection</h3>
          <p>check if the python flask backend is running!</p>
        </div>
      `;
    } finally {
      state.isLoading = false;
    }
  }

  // --- Filtering & Sorting ---
  function applyFilterAndRender() {
    let list = [...state.allGifs];
    const favs = getFavorites();

    // Special Filter: Favorites
    if (state.activeTag === 'favorites') {
      list = list.filter(gif => favs.includes(gif.id));
    } else if (state.activeTag && state.activeTag !== 'all') {
      const tagLower = state.activeTag.toLowerCase();
      list = list.filter(gif => {
        const inTags = (gif.tags || []).some(t => t.toLowerCase() === tagLower);
        const inId = (gif.id || '').toLowerCase().includes(tagLower);
        return inTags || inId;
      });
    }

    // Filter by Search Query
    if (state.searchQuery.trim()) {
      const terms = state.searchQuery.toLowerCase().trim().split(/\s+/);
      list = list.filter(gif => {
        const searchable = [
          gif.title || '',
          gif.id || '',
          (gif.tags || []).join(' ')
        ].join(' ').toLowerCase();
        return terms.every(term => searchable.includes(term));
      });
    }

    // Sorting
    if (state.sortBy === 'oldest') {
      list.reverse();
    } else if (state.sortBy === 'random') {
      list.sort(() => Math.random() - 0.5);
    } else if (state.sortBy === 'title') {
      list.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
    }

    state.filteredGifs = list;
    renderGifsGrid();
    updateResultsInfo();
  }

  // --- Render Functions ---
  function renderGifsGrid() {
    const list = state.filteredGifs;

    if (list.length === 0) {
      el.gifGrid.innerHTML = '';
      el.emptyState.classList.remove('hidden');
      return;
    }

    el.emptyState.classList.add('hidden');

    const fragment = document.createDocumentFragment();

    list.forEach((gif, index) => {
      const card = document.createElement('div');
      card.className = 'gif-card';
      card.setAttribute('data-id', gif.id);
      card.style.animationDelay = `${Math.min(index * 0.03, 0.4)}s`;

      const width = gif.width || 80;
      const height = gif.height || 80;
      const title = gif.title || `${gif.id} gif`;
      const fullUrl = getAbsoluteGifUrl(gif.file);
      const isFav = isFavorite(gif.id);

      // Primary tag pills (up to 2)
      const tagPills = (gif.tags || []).slice(0, 2).map(t => {
        const isCute = t.toLowerCase() === 'cute';
        return `<span class="card-tag-pill ${isCute ? 'tag-cute' : ''}">${t}</span>`;
      }).join('');

      card.innerHTML = `
        <div class="card-washi"></div>
        <button class="card-fav-btn ${isFav ? 'favorited' : ''}" title="${isFav ? 'Remove favorite' : 'Add favorite'}" aria-label="Favorite">
          ${isFav ? '💖' : '♡'}
        </button>
        <div class="card-preview-box">
          <img 
            src="${gif.file}" 
            alt="${escapeHtml(title)}" 
            loading="lazy" 
            class="card-gif-img" 
            width="${width}" 
            height="${height}"
          />
          <span class="card-dim-badge">${width} × ${height} px</span>
        </div>
        <div class="card-info">
          <h3 class="card-title" title="${escapeHtml(title)}">${escapeHtml(title)}</h3>
          <div class="card-tags">
            ${tagPills}
          </div>
          <div class="card-actions">
            <button class="card-btn card-btn-copy" data-url="${fullUrl}" title="Copy direct GIF URL">
              <span>♡</span> Copy
            </button>
            <button class="card-btn card-btn-view" title="Inspect details">
              <span>🔍</span>
            </button>
          </div>
        </div>
      `;

      // Favorite Button Click
      const cardFavBtn = card.querySelector('.card-fav-btn');
      cardFavBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const favorited = toggleFavorite(gif.id);
        cardFavBtn.classList.toggle('favorited', favorited);
        cardFavBtn.innerHTML = favorited ? '💖' : '♡';
        showToast(favorited ? 'added to favorites 💖' : 'removed from favorites ♡');
        renderCategoryPills();
        if (state.activeTag === 'favorites') applyFilterAndRender();
      });

      // Copy Button Click
      const copyBtn = card.querySelector('.card-btn-copy');
      copyBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        copyToClipboard(fullUrl, `copied ${gif.id} URL ♡`);
      });

      // View / Card Click
      card.addEventListener('click', () => {
        openModal(gif, index);
      });

      fragment.appendChild(card);
    });

    el.gifGrid.innerHTML = '';
    el.gifGrid.appendChild(fragment);
  }

  function renderCategoryPills() {
    if (!el.categoryPills) return;
    el.categoryPills.innerHTML = '';

    const favs = getFavorites();
    const tagList = [...state.tags];

    // Prepend Favorites pill if there are favorites
    if (favs.length > 0) {
      tagList.splice(1, 0, { name: 'favorites', count: favs.length });
    }

    tagList.forEach(tagItem => {
      const btn = document.createElement('button');
      btn.className = `cat-pill ${tagItem.name === state.activeTag ? 'active' : ''}`;
      btn.setAttribute('data-tag', tagItem.name);
      
      const icon = getTagIcon(tagItem.name);
      btn.innerHTML = `<span class="pill-sparkle">${icon}</span> ${tagItem.name} <span class="pill-count">(${tagItem.count})</span>`;

      btn.addEventListener('click', () => {
        setActiveTag(tagItem.name);
      });

      el.categoryPills.appendChild(btn);
    });
  }

  function renderCategoryDrawer() {
    if (!el.categoriesGrid) return;
    el.categoriesGrid.innerHTML = '';

    state.tags.forEach(tagItem => {
      if (tagItem.name === 'all') return;
      const card = document.createElement('div');
      card.className = 'category-browser-card';
      card.innerHTML = `
        <div class="cat-browser-icon">${getTagIcon(tagItem.name)}</div>
        <div class="cat-browser-name">${tagItem.name}</div>
        <div class="cat-browser-count">${tagItem.count} gifs</div>
      `;

      card.addEventListener('click', () => {
        setActiveTag(tagItem.name);
        const exploreSection = document.getElementById('explore');
        if (exploreSection) {
          exploreSection.scrollIntoView({ behavior: 'smooth' });
        }
      });

      el.categoriesGrid.appendChild(card);
    });
  }

  function updateResultsInfo() {
    if (!el.resultsCount) return;
    const count = state.filteredGifs.length;
    let tagName = 'all categories';
    if (state.activeTag === 'favorites') tagName = '💖 favorites';
    else if (state.activeTag !== 'all') tagName = `#${state.activeTag}`;
    
    if (state.searchQuery.trim()) {
      el.resultsCount.textContent = `Found ${count} gif(s) for "${state.searchQuery}" in ${tagName}`;
    } else {
      el.resultsCount.textContent = `Showing ${count} gif(s) in ${tagName}`;
    }
  }

  function setActiveTag(tagName) {
    state.activeTag = tagName;
    
    const pills = el.categoryPills.querySelectorAll('.cat-pill');
    pills.forEach(p => {
      if (p.getAttribute('data-tag') === tagName) {
        p.classList.add('active');
        p.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
      } else {
        p.classList.remove('active');
      }
    });

    applyFilterAndRender();
  }

  // --- Modal Logic & Carousel Navigation ---
  function openModal(gif, index = -1) {
    state.selectedGif = gif;
    if (index >= 0) {
      state.selectedGifIndex = index;
    } else {
      state.selectedGifIndex = state.filteredGifs.findIndex(g => g.id === gif.id);
    }

    const fullUrl = getAbsoluteGifUrl(gif.file);

    el.modalImg.src = gif.file;
    el.modalImg.alt = gif.title || gif.id;
    el.modalTitle.textContent = gif.title || `${gif.id} GIF`;
    
    const dimsText = `${gif.width || 80} × ${gif.height || 80} px`;
    el.modalDims.textContent = dimsText;
    el.modalDimBadge.textContent = dimsText;

    // Favorite state in modal
    const isFav = isFavorite(gif.id);
    el.modalFavBtn.classList.toggle('favorited', isFav);
    el.modalFavBtn.innerHTML = isFav ? '💖' : '♡';

    // Format file size
    const sizeKb = (gif.file_size / 1024).toFixed(1);
    el.modalSize.textContent = `${sizeKb} KB`;
    el.modalId.textContent = gif.id;

    // Source info
    if (gif.source_url) {
      el.modalSource.innerHTML = `<a href="${gif.source_url}" target="_blank" rel="noopener noreferrer">GIPHY ↗</a>`;
      el.modalSourceRow.classList.remove('hidden');
    } else if (gif.source === 'procedural') {
      el.modalSource.textContent = 'Kawaii Procedural Sticker';
      el.modalSourceRow.classList.remove('hidden');
    } else {
      el.modalSourceRow.classList.add('hidden');
    }

    // Modal Tags
    el.modalTags.innerHTML = (gif.tags || []).map(t => {
      return `<span class="card-tag-pill ${t.toLowerCase() === 'cute' ? 'tag-cute' : ''}">#${t}</span>`;
    }).join('');

    // Direct URL & Download
    el.modalUrlInput.value = fullUrl;
    el.modalDownloadBtn.href = gif.file;
    el.modalDownloadBtn.setAttribute('download', `${gif.id}.gif`);

    el.modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function navigateModal(direction) {
    if (!state.selectedGif || state.filteredGifs.length === 0) return;
    let newIndex = state.selectedGifIndex + direction;
    if (newIndex < 0) newIndex = state.filteredGifs.length - 1;
    if (newIndex >= state.filteredGifs.length) newIndex = 0;

    const nextGif = state.filteredGifs[newIndex];
    if (nextGif) {
      openModal(nextGif, newIndex);
    }
  }

  function closeModal() {
    el.modal.classList.add('hidden');
    document.body.style.overflow = '';
    state.selectedGif = null;
    state.selectedGifIndex = -1;
  }

  // --- Surprise Me Random GIF ---
  function surpriseMe() {
    if (state.allGifs.length === 0) return;
    const randomIndex = Math.floor(Math.random() * state.allGifs.length);
    const randomGif = state.allGifs[randomIndex];
    openModal(randomGif);
    showToast('✨ surprise gif! ♡');
  }

  // --- Toast Notifications ---
  let toastTimeout = null;
  function showToast(message = 'copied to clipboard ♡') {
    if (!el.toast) return;
    el.toastText.textContent = message;
    el.toast.classList.remove('hidden');

    if (toastTimeout) clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
      el.toast.classList.add('hidden');
    }, 2400);
  }

  // --- Clipboard Helpers ---
  async function copyToClipboard(text, successMsg = 'copied to clipboard ♡') {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      showToast(successMsg);
    } catch (e) {
      console.warn('Clipboard write failed:', e);
      showToast('copied ♡');
    }
  }

  function getAbsoluteGifUrl(relativePath) {
    const origin = window.location.origin;
    return `${origin}${relativePath}`;
  }

  function escapeHtml(str) {
    return (str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --- Event Listeners ---
  function setupEventListeners() {
    // Search input
    el.searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value;
      if (state.searchQuery.length > 0) {
        el.searchClearBtn.classList.add('visible');
      } else {
        el.searchClearBtn.classList.remove('visible');
      }
      applyFilterAndRender();
    });

    // Clear search
    el.searchClearBtn.addEventListener('click', () => {
      el.searchInput.value = '';
      state.searchQuery = '';
      el.searchClearBtn.classList.remove('visible');
      el.searchInput.focus();
      applyFilterAndRender();
    });

    // Reset search on empty state
    if (el.resetSearchBtn) {
      el.resetSearchBtn.addEventListener('click', () => {
        el.searchInput.value = '';
        state.searchQuery = '';
        state.activeTag = 'all';
        el.searchClearBtn.classList.remove('visible');
        renderCategoryPills();
        applyFilterAndRender();
      });
    }

    // Sort select
    el.sortSelect.addEventListener('change', (e) => {
      state.sortBy = e.target.value;
      applyFilterAndRender();
    });

    // Surprise Me
    if (el.surpriseBtn) {
      el.surpriseBtn.addEventListener('click', surpriseMe);
    }

    // Theme Switcher
    if (el.themeBtn) {
      el.themeBtn.addEventListener('click', cycleTheme);
    }

    // Modal navigation arrows
    if (el.modalPrevBtn) {
      el.modalPrevBtn.addEventListener('click', () => navigateModal(-1));
    }
    if (el.modalNextBtn) {
      el.modalNextBtn.addEventListener('click', () => navigateModal(1));
    }

    // Modal Favorite Button
    if (el.modalFavBtn) {
      el.modalFavBtn.addEventListener('click', () => {
        if (!state.selectedGif) return;
        const favorited = toggleFavorite(state.selectedGif.id);
        el.modalFavBtn.classList.toggle('favorited', favorited);
        el.modalFavBtn.innerHTML = favorited ? '💖' : '♡';
        showToast(favorited ? 'added to favorites 💖' : 'removed from favorites ♡');
        renderCategoryPills();
        renderGifsGrid();
      });
    }

    // Modal Copy Formats
    if (el.copyMarkdownBtn) {
      el.copyMarkdownBtn.addEventListener('click', () => {
        if (!state.selectedGif) return;
        const url = getAbsoluteGifUrl(state.selectedGif.file);
        const md = `![${state.selectedGif.title || state.selectedGif.id}](${url})`;
        copyToClipboard(md, 'Markdown tag copied ♡');
      });
    }
    if (el.copyHtmlBtn) {
      el.copyHtmlBtn.addEventListener('click', () => {
        if (!state.selectedGif) return;
        const url = getAbsoluteGifUrl(state.selectedGif.file);
        const html = `<img src="${url}" alt="${state.selectedGif.title || state.selectedGif.id}" width="${state.selectedGif.width}" height="${state.selectedGif.height}" />`;
        copyToClipboard(html, 'HTML img tag copied ♡');
      });
    }
    if (el.copyDiscordBtn) {
      el.copyDiscordBtn.addEventListener('click', () => {
        if (!state.selectedGif) return;
        const url = getAbsoluteGifUrl(state.selectedGif.file);
        copyToClipboard(url, 'Discord link copied ♡');
      });
    }

    // Modal close events
    el.modalCloseBtn.addEventListener('click', closeModal);
    el.modal.addEventListener('click', (e) => {
      if (e.target === el.modal) closeModal();
    });

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
      // Escape closes modal
      if (e.key === 'Escape') {
        if (!el.modal.classList.contains('hidden')) {
          closeModal();
        } else if (document.activeElement === el.searchInput && el.searchInput.value) {
          el.searchInput.value = '';
          state.searchQuery = '';
          el.searchClearBtn.classList.remove('visible');
          applyFilterAndRender();
        }
      }
      
      // Arrow keys inside modal
      if (!el.modal.classList.contains('hidden')) {
        if (e.key === 'ArrowLeft') {
          navigateModal(-1);
        } else if (e.key === 'ArrowRight') {
          navigateModal(1);
        }
      }

      // '/' to focus search when not in an input
      if (e.key === '/' && document.activeElement !== el.searchInput && el.modal.classList.contains('hidden')) {
        e.preventDefault();
        el.searchInput.focus();
        el.searchInput.select();
      }
    });

    // Modal Copy Buttons
    el.modalCopyUrlBtn.addEventListener('click', () => {
      copyToClipboard(el.modalUrlInput.value, 'direct URL copied ♡');
    });
    el.modalMainCopyBtn.addEventListener('click', () => {
      copyToClipboard(el.modalUrlInput.value, 'GIF link copied ♡');
    });

    // Navigation Smooth Scroll & Active Tracking
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        const targetId = link.getAttribute('href');
        if (targetId.startsWith('#')) {
          e.preventDefault();
          const targetEl = document.querySelector(targetId);
          if (targetEl) {
            targetEl.scrollIntoView({ behavior: 'smooth' });
          }
          navLinks.forEach(l => l.classList.remove('active'));
          link.classList.add('active');
        }
      });
    });
  }

  function handleHashNavigation() {
    const hash = window.location.hash.replace('#', '');
    if (hash && hash !== 'home' && hash !== 'explore' && hash !== 'categories' && hash !== 'about') {
      setActiveTag(decodeURIComponent(hash));
    }
  }

  // --- Kawaii Canvas Floating Background Particles ---
  function initCanvasParticles() {
    const canvas = el.bgCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    window.addEventListener('resize', () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    });

    const particles = [];
    const numParticles = 28;
    const symbols = ['✦', '✧', '★', '♡', '🌸', '✨'];
    const colors = ['#ffd1dc', '#ffe4e8', '#e8e0f8', '#d4eaf7', '#fff2b2'];

    for (let i = 0; i < numParticles; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        symbol: symbols[Math.floor(Math.random() * symbols.length)],
        color: colors[Math.floor(Math.random() * colors.length)],
        size: Math.random() * 12 + 10,
        vx: (Math.random() - 0.5) * 0.4,
        vy: - (Math.random() * 0.4 + 0.2),
        opacity: Math.random() * 0.5 + 0.2,
        rot: Math.random() * Math.PI * 2,
        vRot: (Math.random() - 0.5) * 0.02
      });
    }

    function animate() {
      ctx.clearRect(0, 0, width, height);

      particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        p.rot += p.vRot;

        if (p.y < -30) {
          p.y = height + 30;
          p.x = Math.random() * width;
        }
        if (p.x < -30) p.x = width + 30;
        if (p.x > width + 30) p.x = -30;

        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.opacity;
        ctx.font = `${p.size}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(p.symbol, 0, 0);
        ctx.restore();
      });

      requestAnimationFrame(animate);
    }

    animate();
  }

  // Run on DOM Ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
