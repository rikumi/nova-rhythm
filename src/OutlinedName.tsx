import { useLayoutEffect, useRef, useState } from 'react';

export function OutlinedName({ text }: { text: string }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const textRef = useRef<SVGTextElement>(null);
  const [box, setBox] = useState({ width: 1, height: 34 });
  useLayoutEffect(() => {
    const svg = svgRef.current, label = textRef.current;
    if (!svg || !label) return;
    const measure = () => {
      const bounds = svg.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return;
      const next = { width: Math.max(bounds.width, label.getComputedTextLength() + 6), height: bounds.height };
      setBox(previous => previous.width === next.width && previous.height === next.height ? previous : next);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(svg);
    document.fonts.addEventListener('loadingdone', measure);
    return () => { observer.disconnect(); document.fonts.removeEventListener('loadingdone', measure); };
  }, [text]);
  return <svg ref={svgRef} className="outlined-name" viewBox={`0 0 ${box.width} ${box.height}`} preserveAspectRatio="xMinYMid meet" aria-hidden="true"><text ref={textRef} x="3" y={box.height / 2} dy=".35em">{text}</text></svg>;
}
