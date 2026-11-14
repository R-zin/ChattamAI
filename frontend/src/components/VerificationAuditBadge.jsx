import React, { useState } from 'react'
import Icon from './Icon.jsx'

export default function VerificationAuditBadge({ verification, className = '' }) {
  const [expanded, setExpanded] = useState(false)

  if (!verification) return null

  const status = verification.status || 'skipped'
  const modelName = verification.verified_by_model || 'Secondary Verifier'
  const confidence =
    typeof verification.confidence_score === 'number'
      ? `${Math.round(verification.confidence_score * 100)}%`
      : null
  const discrepancies = Array.isArray(verification.discrepancies)
    ? verification.discrepancies
    : []
  const resolvedCount = discrepancies.length

  // Determine badge style and labels based on status
  let badgeConfig = {
    label: 'Single Model Audited',
    icon: 'info',
    badgeClass: 'border-line bg-surface text-ink-2 hover:border-line-strong',
    iconColor: 'text-ink-2',
    isActionable: false,
  }

  if (status === 'confirmed') {
    badgeConfig = {
      label: `Double-Checked & Confirmed by ${modelName}`,
      icon: 'check-circle',
      badgeClass:
        'border-ok/40 bg-ok/10 text-ok hover:border-ok/60',
      iconColor: 'text-ok',
      isActionable: true,
    }
  } else if (status === 'flagged_discrepancy' || status === 'adjusted') {
    badgeConfig = {
      label: `Discrepancies Reconciled (${resolvedCount} resolved)`,
      icon: 'alert-triangle',
      badgeClass:
        'border-warn/40 bg-warn/10 text-warn hover:border-warn/60',
      iconColor: 'text-warn',
      isActionable: true,
    }
  } else if (status === 'skipped') {
    badgeConfig = {
      label: 'Single Model Audited',
      sublabel: 'Verifier Skipped',
      icon: 'shield',
      badgeClass: 'border-line bg-surface text-ink-2 hover:border-line-strong',
      iconColor: 'text-ink-3',
      isActionable: Boolean(verification.cross_check_notes || verification.reason),
    }
  } else if (status === 'error') {
    badgeConfig = {
      label: 'Verifier Offline (Using Primary Findings)',
      icon: 'alert-triangle',
      badgeClass:
        'border-danger/40 bg-danger/10 text-danger hover:border-danger/60',
      iconColor: 'text-danger',
      isActionable: Boolean(verification.error),
    }
  }

  const typeMeta = {
    false_positive: {
      label: 'FALSE POSITIVE',
      bg: 'bg-ok/10 border-ok/40 text-ok',
    },
    hallucination: {
      label: 'HALLUCINATION',
      bg: 'bg-surface-3 border-line-strong text-ink',
    },
    missed_violation: {
      label: 'MISSED VIOLATION',
      bg: 'bg-danger/10 border-danger/40 text-danger',
    },
    value_mismatch: {
      label: 'VALUE MISMATCH',
      bg: 'bg-warn/10 border-warn/40 text-warn',
    },
  }

  return (
    <div className={`font-sans ${className}`} data-testid="verification-audit-badge">
      {/* Badge button / header */}
      <div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(e) =>
          (e.key === 'Enter' || e.key === ' ') && setExpanded(!expanded)
        }
        className={`inline-flex items-center gap-2.5 px-3 py-1.5 border text-xs font-mono transition-all cursor-pointer select-none rounded-sm ${badgeConfig.badgeClass}`}
      >
        <Icon
          name={badgeConfig.icon}
          className={`text-sm shrink-0 ${badgeConfig.iconColor}`}
        />
        <span className="font-semibold tracking-tight">{badgeConfig.label}</span>
        {confidence && status === 'confirmed' && (
          <span className="text-[10px] bg-surface px-1.5 py-0.5 rounded border border-current/30 font-semibold tabular-nums">
            {confidence}
          </span>
        )}
        <Icon
          name={expanded ? 'chevron-up' : 'chevron-down'}
          className="text-xs opacity-60 ml-0.5"
        />
      </div>

      {/* Expandable details drawer / card */}
      {expanded && (
        <div
          data-testid="verification-details-card"
          className="mt-3 p-4 bg-inset border border-line rounded-sm text-xs space-y-4 shadow-xl"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2.5">
            <div className="flex items-center gap-2 mono text-[11px] text-ink-2">
              <span className="uppercase text-ink-3">AUDITING ENGINE:</span>
              <span className="text-ink font-medium">{modelName}</span>
              {confidence && (
                <>
                  <span className="text-ink-3">|</span>
                  <span className="uppercase text-ink-3">CONFIDENCE:</span>
                  <span className="text-ink font-medium">{confidence}</span>
                </>
              )}
            </div>
            {verification.primary_violations_count !== undefined && (
              <div className="mono text-[10px] text-ink-3">
                <span>Primary: {verification.primary_violations_count}</span>
                <span className="mx-1.5">→</span>
                <span>
                  Vetted:{' '}
                  {verification.final_violations_count ??
                    verification.primary_violations_count}
                </span>
              </div>
            )}
          </div>

          {/* Cross check notes */}
          {verification.cross_check_notes && (
            <div className="bg-surface p-3 border-l-2 border-line-strong space-y-1">
              <div className="text-[10px] mono text-ink-3 uppercase tracking-wider font-semibold">
                AUDITOR CROSS-EXAMINATION NOTES
              </div>
              <p className="text-xs text-ink-2 leading-relaxed">
                {verification.cross_check_notes}
              </p>
            </div>
          )}

          {/* Reason or error message when skipped or failed */}
          {verification.reason && (
            <p className="text-xs text-ink-3 font-mono">
              Status info: {verification.reason}
            </p>
          )}
          {verification.error && (
            <div className="p-2.5 bg-danger/10 border border-danger/40 text-danger text-xs font-mono">
              Verifier error details: {verification.error}
            </div>
          )}

          {/* Discrepancies listing */}
          {discrepancies.length > 0 && (
            <div className="space-y-3 pt-1">
              <div className="text-[10px] mono text-ink-3 uppercase tracking-wider font-bold">
                RECONCILED DISCREPANCIES ({discrepancies.length})
              </div>
              <div className="space-y-2.5">
                {discrepancies.map((d, idx) => {
                  const typeInfo = typeMeta[d.type] || {
                    label: d.type ? d.type.toUpperCase() : 'DISCREPANCY',
                    bg: 'bg-surface-3 border-line-strong text-ink-2',
                  }
                  return (
                    <div
                      key={idx}
                      className="p-3 bg-surface border border-line rounded-sm space-y-2"
                    >
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="mono font-semibold text-ink text-xs">
                          {d.rule_reference || 'Statutory Reference'}
                        </span>
                        <span
                          className={`text-[9px] mono px-2 py-0.5 border font-medium ${typeInfo.bg}`}
                        >
                          {typeInfo.label}
                        </span>
                      </div>
                      <p className="text-xs text-ink-2 leading-relaxed">
                        {d.description}
                      </p>
                      {(d.primary_finding || d.verifier_finding) && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                          <div className="p-2 bg-inset border border-line">
                            <div className="text-[9px] text-ink-3 uppercase tracking-wider mb-0.5">
                              PRIMARY FINDING
                            </div>
                            <div className="text-ink-2">
                              {d.primary_finding || 'None'}
                            </div>
                          </div>
                          <div className="p-2 bg-inset border border-line">
                            <div className="text-[9px] text-ink uppercase tracking-wider mb-0.5">
                              VERIFIER FINDING
                            </div>
                            <div className="text-ink font-medium">
                              {d.verifier_finding || 'None'}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
