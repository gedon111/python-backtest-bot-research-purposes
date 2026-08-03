import { useMemo } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

interface LatexProps {
  /** TeX source. Always an author-supplied constant in this app, never user input. */
  tex: string;
  block?: boolean;
  className?: string;
}

/** Renders a TeX string via KaTeX (sync, no CDN, ~lighter than MathJax). */
export function Latex({ tex, block = false, className }: LatexProps) {
  const html = useMemo(
    () => katex.renderToString(tex, { throwOnError: false, displayMode: block }),
    [tex, block],
  );
  const Tag = block ? 'div' : 'span';
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
