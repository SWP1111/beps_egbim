export function attachCustomScrollbar(scrollTarget, scrollbarEl, thumbEl) {
  const updateThumbHeight = () => {
    const scrollable = scrollTarget.scrollHeight - scrollTarget.clientHeight;
    if (scrollable <= 0) {
      thumbEl.style.display = 'none';
      scrollbarEl.style.display = 'none';
    } else {
      thumbEl.style.display = 'block';
      scrollbarEl.style.display = 'block';
      const ratio = scrollTarget.clientHeight / scrollTarget.scrollHeight;
      const height = ratio * scrollbarEl.clientHeight;
      thumbEl.style.height = `${height}px`;
    }
  };

  const updateThumbPosition = () => {
    const ratio = scrollTarget.scrollTop / (scrollTarget.scrollHeight - scrollTarget.clientHeight);
    const maxTop = scrollbarEl.clientHeight - thumbEl.offsetHeight;
    const top = ratio * maxTop;
    thumbEl.style.transform = `translateY(${top}px)`;
  };

  const updateThumbVisibility = () => {
    const scrollable = scrollTarget.scrollHeight > scrollTarget.clientHeight;
    if (scrollable) {
      scrollbarEl.style.display = 'block';
      updateThumbHeight();
      updateThumbPosition();
    } else {
      scrollbarEl.style.display = 'none';
    }
  };

  scrollTarget.addEventListener('scroll', () => {
    updateThumbHeight();
    updateThumbPosition();
    updateThumbVisibility();
  });

  // 드래그
  let isDragging = false;
  let startY, startScrollTop;

  thumbEl.addEventListener('mousedown', (e) => {
    isDragging = true;
    startY = e.clientY;
    startScrollTop = scrollTarget.scrollTop;
    e.preventDefault();
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const deltaY = e.clientY - startY;
    const maxTop = scrollbarEl.clientHeight - thumbEl.offsetHeight;
    const scrollRatio = (scrollTarget.scrollHeight - scrollTarget.clientHeight) / maxTop;
    scrollTarget.scrollTop = startScrollTop + deltaY * scrollRatio;
  });

  document.addEventListener('mouseup', () => {
    isDragging = false;
  });

  // 초기 상태 적용
  requestAnimationFrame(() => {
    //updateThumbHeight();
    //updateThumbPosition();
    updateThumbVisibility();
  });

  return {
    refresh: () => {
      //updateThumbHeight();
      //updateThumbPosition();
      updateThumbVisibility();
    }
  };
}
