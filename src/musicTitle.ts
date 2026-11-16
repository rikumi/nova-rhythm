export function musicTitleParts(name: string): { title: string; subtitle?: string } {
  const value = name.trim();
  const pairs: Record<string, string> = { ')': '(', '）': '（' };
  const end = value.at(-1) || '';
  if (!pairs[end]) return { title: name };
  const stack: string[] = [];
  for (let i = value.length - 1; i >= 0; i--) {
    const char = value[i];
    if (pairs[char]) stack.push(pairs[char]);
    else if (char === '(' || char === '（') {
      if (stack.pop() !== char) return { title: name };
      if (!stack.length) {
        const title = value.slice(i + 1, -1).trim(), subtitle = value.slice(0, i).trim();
        return title && subtitle ? { title, subtitle } : { title: name };
      }
    }
  }
  return { title: name };
}
