export function updateSectionUi(section: HTMLElement, expanded: boolean): void {
  section.classList.toggle('is-collapsed', !expanded);
  section.setAttribute('data-expanded', expanded ? 'true' : 'false');

  const toggle = section.querySelector<HTMLButtonElement>(':scope > .control-section-toggle');
  const body = section.querySelector<HTMLElement>(':scope > .control-section-body');
  toggle?.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  if (body) {
    body.hidden = !expanded;
  }
}

function createSectionToggle(section: HTMLElement, title: string): HTMLButtonElement {
  const badge = section.dataset.menuBadge?.trim() ?? '';

  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'control-section-toggle';

  const titleRow = document.createElement('span');
  titleRow.className = 'control-section-title-row';

  const titleLabel = document.createElement('span');
  titleLabel.className = 'control-section-title';
  titleLabel.textContent = title;
  titleRow.appendChild(titleLabel);

  if (badge) {
    const badgeEl = document.createElement('span');
    badgeEl.className = 'control-section-badge';
    badgeEl.textContent = badge;
    titleRow.appendChild(badgeEl);
  }

  const chevron = document.createElement('span');
  chevron.className = 'control-section-chevron';
  chevron.setAttribute('aria-hidden', 'true');
  chevron.textContent = '▾';

  toggle.append(titleRow, chevron);
  return toggle;
}

export function decorateSection(section: HTMLElement): void {
  if (section.dataset.menuEnhanced === 'true') {
    return;
  }

  const heading = section.querySelector<HTMLHeadingElement>(':scope > h3');
  if (!heading) {
    return;
  }

  const title = heading.textContent?.trim() || section.id;
  const body = document.createElement('div');
  body.className = 'control-section-body';

  let sibling = heading.nextSibling;
  while (sibling) {
    const next = sibling.nextSibling;
    body.appendChild(sibling);
    sibling = next;
  }

  const toggle = createSectionToggle(section, title);
  heading.remove();
  section.prepend(toggle);
  section.appendChild(body);
  section.dataset.menuEnhanced = 'true';
}
