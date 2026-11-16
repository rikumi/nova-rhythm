import { useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';

export function ScrollingText({ text, className = '' }: { text: string; className?: string }) {
  const viewport = useRef<HTMLSpanElement>(null);
  const content = useRef<HTMLSpanElement>(null);
  const [distance, setDistance] = useState(0);
  useLayoutEffect(() => {
    const outer = viewport.current, inner = content.current;
    if (!outer || !inner) return;
    const measure = () => {
      const width = inner.getBoundingClientRect().width;
      setDistance(outer.clientWidth > 0 && width > outer.clientWidth + 1 ? width + 32 : 0);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(outer); observer.observe(inner);
    return () => observer.disconnect();
  }, [text]);
  return <span ref={viewport} className={`scrolling-subtitle ${className} ${distance ? 'is-overflowing' : ''}`} title={text}
    style={{ '--scroll-distance': `${distance}px`, '--scroll-duration': `${Math.max(12, distance / 24)}s` } as CSSProperties}>
    <span className="scrolling-subtitle-track" key={text}><span ref={content}>{text}</span>{distance > 0 && <span aria-hidden="true">{text}</span>}</span>
  </span>;
}
