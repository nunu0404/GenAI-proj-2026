/** 입력창·편집 가능한 영역에 포커스가 있으면 방향키를 슬라이드 이동으로 처리하지 않는다. */
export function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el || typeof el.closest !== "function") return false;
  if (el.isContentEditable) return true;
  return !!el.closest('input, textarea, select, [contenteditable=""], [contenteditable="true"], [role="textbox"]');
}
