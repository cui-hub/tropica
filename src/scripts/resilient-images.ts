const retryDelays = [700, 1800];

function prepareImage(image: HTMLImageElement) {
  const frame = image.closest<HTMLElement>('[data-image-frame]');
  if (!frame || image.dataset.resilientReady === 'true') return;

  image.dataset.resilientReady = 'true';
  image.dataset.originalSrc = image.getAttribute('src') || image.src;
  image.dataset.retryCount = '0';

  const showImage = () => {
    delete image.dataset.retryPending;
    frame.classList.remove('is-image-retrying', 'is-image-unavailable');
    frame.removeAttribute('aria-busy');
  };

  const retryImage = () => {
    if (image.dataset.retryPending === 'true') return;

    const retryCount = Number(image.dataset.retryCount || '0');
    if (retryCount >= retryDelays.length) {
      frame.classList.remove('is-image-retrying');
      frame.classList.add('is-image-unavailable');
      frame.removeAttribute('aria-busy');
      return;
    }

    image.dataset.retryPending = 'true';
    image.dataset.retryCount = String(retryCount + 1);
    frame.classList.remove('is-image-unavailable');
    frame.classList.add('is-image-retrying');
    frame.setAttribute('aria-busy', 'true');

    const jitter = Math.floor(Math.random() * 300);
    window.setTimeout(() => {
      delete image.dataset.retryPending;
      if (!image.isConnected) return;

      const retryUrl = new URL(image.dataset.originalSrc || image.src, window.location.href);
      retryUrl.searchParams.set('__image_retry', String(retryCount + 1));
      image.src = retryUrl.href;
    }, retryDelays[retryCount] + jitter);
  };

  image.addEventListener('load', showImage);
  image.addEventListener('error', retryImage);

  // The script is deferred, so an eager image may have failed before listeners were attached.
  if (image.complete && image.naturalWidth === 0) retryImage();
}

document.querySelectorAll<HTMLImageElement>('img[data-resilient-image]').forEach(prepareImage);
