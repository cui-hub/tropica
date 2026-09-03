const storageKey = 'aquatic-wiki:favorites:v1';

function readFavorites() {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey) || '[]');
    return new Set<string>(Array.isArray(value) ? value : []);
  } catch {
    return new Set<string>();
  }
}

function writeFavorites(favorites: Set<string>) {
  localStorage.setItem(storageKey, JSON.stringify([...favorites]));
}

function syncFavorites() {
  const favorites = readFavorites();
  document.querySelectorAll<HTMLElement>('[data-favorite]').forEach((button) => {
    const active = favorites.has(button.dataset.favorite || '');
    button.setAttribute('aria-pressed', String(active));
    button.setAttribute('aria-label', active ? '取消收藏' : '加入收藏');
    const icon = button.querySelector('span');
    const label = button.querySelector('em');
    if (icon) icon.textContent = active ? '♥' : '♡';
    if (label) label.textContent = active ? '已收藏' : '收藏';
  });
  document.dispatchEvent(new CustomEvent('aquatic:favorites', { detail: favorites }));
}

document.addEventListener('click', (event) => {
  const button = (event.target as HTMLElement).closest<HTMLElement>('[data-favorite]');
  if (!button) return;
  const favorites = readFavorites();
  const key = button.dataset.favorite || '';
  favorites.has(key) ? favorites.delete(key) : favorites.add(key);
  writeFavorites(favorites);
  syncFavorites();
});

syncFavorites();
