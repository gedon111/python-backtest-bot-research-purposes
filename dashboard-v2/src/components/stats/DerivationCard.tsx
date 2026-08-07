import { Latex } from '../common/Latex';
import type { DerivationStep } from './derivationSteps';

/**
 * One reusable card for every derivation instance (19 across the Solutions
 * tab: 1 binomial + 5 Fisher + 5 Welch + 5 MDE + 1 bootstrap + 1 Pearson + 1
 * Spearman) -- driven entirely by a DerivationStep, so instance count comes
 * from .map() over live statsCompute.ts data, not from hand-writing 19
 * components. Order: variables -> general formula -> substitution -> result,
 * per the requested "variables first, then the actual solution" format.
 */
export function DerivationCard({ step }: { step: DerivationStep }) {
  return (
    <div className="derivation-card">
      <h4 className="derivation-title">{step.title}</h4>

      <div className="derivation-section">
        <span className="derivation-label">Variables</span>
        <ul className="derivation-vars">
          {step.variables.map((v) => (
            <li key={v.symbol}>
              <Latex tex={`${v.symbol} = ${v.value}`} />
              <span className="text-muted"> -- {v.description}</span>
            </li>
          ))}
        </ul>
      </div>

      {step.variableDerivations && step.variableDerivations.length > 0 && (
        <div className="derivation-section">
          <span className="derivation-label">How The Variables Above Were Computed</span>
          <div className="derivation-subcards">
            {step.variableDerivations.map((vd) => (
              <div key={vd.symbol} className="derivation-subcard">
                <Latex tex={vd.symbol} />
                <span className="text-muted"> -- {vd.description}</span>
                <Latex block className="derivation-formula" tex={vd.formulaTex} />
                <Latex block className="derivation-formula" tex={vd.substitutedTex} />
                <Latex block className="derivation-result" tex={vd.resultTex} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="derivation-section">
        <span className="derivation-label">General Formula</span>
        <Latex block className="derivation-formula" tex={step.generalFormulaTex} />
      </div>

      <div className="derivation-section">
        <span className="derivation-label">Substitution</span>
        <Latex block className="derivation-formula" tex={step.substitutedFormulaTex} />
      </div>

      <div className="derivation-section">
        <span className="derivation-label">Result</span>
        <Latex block className="derivation-result" tex={step.resultTex} />
      </div>

      <p className="derivation-prose text-muted">{step.prose}</p>
    </div>
  );
}
