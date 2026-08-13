import { Latex } from '../common/Latex';
import type { DerivationBlock, DerivationStep, DerivationTable } from './derivationSteps';

/**
 * One reusable card for every derivation instance -- driven entirely by a
 * DerivationStep's ordered `steps` list, each an ordered list of `blocks`.
 * Blocks (not fixed formula/table/note fields) exist because different
 * derivations need different internal orderings: Welch's step 1 wants its
 * raw-value TABLE before the mean FORMULA, while Fisher's enumeration step
 * wants the hypergeometric FORMULA before its term TABLE. A fixed field
 * order can't express both; an ordered block list can.
 */
export function DerivationCard({ step }: { step: DerivationStep }) {
  return (
    <div className="derivation-card" id={step.id}>
      <h4 className="derivation-title">{step.title}</h4>

      {step.steps.map((line, i) => (
        <div key={`${line.label}-${i}`} className="derivation-step">
          <div className="derivation-step-header">
            <span className="derivation-step-num">Step {i + 1}</span>
            <span className="derivation-step-label">{line.label}</span>
          </div>
          {line.description && <p className="derivation-step-desc text-muted">{line.description}</p>}
          {line.blocks.map((block, bIdx) => (
            <DerivationBlockView key={bIdx} block={block} />
          ))}
        </div>
      ))}

      <div className="derivation-section">
        <span className="derivation-label">Result</span>
        <Latex block className="derivation-result" tex={step.resultTex} />
      </div>

      <p className="derivation-prose text-muted">{step.prose}</p>
    </div>
  );
}

function DerivationBlockView({ block }: { block: DerivationBlock }) {
  switch (block.kind) {
    case 'values':
      return (
        <ul className="derivation-vars">
          {block.items.map((v) => (
            <li key={v.symbol}>
              <Latex tex={`${v.symbol} = ${v.value}`} />
              <span className="text-muted"> -- {v.description}</span>
            </li>
          ))}
        </ul>
      );
    case 'algebra':
      return (
        <>
          <Latex block className="derivation-formula" tex={block.formulaTex} />
          {block.substitutedTex && <Latex block className="derivation-formula" tex={block.substitutedTex} />}
          {block.resultTex && <Latex block className="derivation-result" tex={block.resultTex} />}
        </>
      );
    case 'table':
      return <DerivationTableView table={block.table} />;
    case 'note':
      return <p className={`derivation-note text-muted${block.tone === 'caveat' ? ' derivation-note-caveat' : ''}`}>{block.text}</p>;
    case 'crosscheck':
      return (
        <div className={`derivation-crosscheck ${block.match ? 'match' : 'mismatch'}`}>
          <span className={`tag ${block.match ? 'tag-good' : 'tag-critical'}`}>{block.match ? 'MATCH' : 'MISMATCH'}</span>
          <span className="derivation-crosscheck-values">
            {block.label}: JS = {block.jsValue}, Python = {block.pyValue}
          </span>
          <span className="text-muted derivation-crosscheck-source"> -- {block.source}</span>
        </div>
      );
    default:
      return null;
  }
}

function DerivationTableView({ table }: { table: DerivationTable }) {
  const collapsed = table.collapsed ?? true;
  const body = (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            {table.headers.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, i) => (
            <tr key={i} className={row.emphasis ? `derivation-row-${row.emphasis}` : undefined}>
              {row.cells.map((c, j) => (
                <td key={j}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  if (!collapsed) return body;
  return (
    <details className="derivation-table-details">
      <summary>{table.caption}</summary>
      {body}
    </details>
  );
}
