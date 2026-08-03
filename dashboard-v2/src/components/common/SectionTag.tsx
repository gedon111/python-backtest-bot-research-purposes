import './SectionTag.css';

export function SectionTag({ kind }: { kind: 'live' | 'reference' }) {
  return <span className={`section-tag ${kind}`}>{kind === 'live' ? 'Live' : 'Reference'}</span>;
}
