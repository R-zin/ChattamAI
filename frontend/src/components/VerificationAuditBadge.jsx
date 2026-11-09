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
    badgeClass: 'border-[#333333] bg-[#141414] text-[#a3a3a3] hover:border-[#555555]',
    iconColor: 'text-[#a3a3a3]',
    isActionable: false,
  }

  if (status === 'confirmed') {
    badgeConfig = {
      label: `Double-Checked & Confirmed by ${modelName}`,
      icon: 'check-circle',
      badgeClass:
        'border-emerald-600/40 bg-emerald-950/20 text-emerald-400 hover:border-emerald-500/60',
      iconColor: 'text-emerald-400',
      isActionable: true,
    }
  } else if (status === 'flagged_discrepancy' || status === 'adjusted') {
    badgeConfig = {
      label: `Discrepancies Reconciled (${resolvedCount} resolved)`,
      icon: 'alert-triangle',
      badgeClass:
        'border-amber-600/40 bg-amber-950/20 text-amber-400 hover:border-amber-500/60',
      iconColor: 'text-amber-400',
      isActionable: true,
    }
  } else if (status === 'skipped') {
    badgeConfig = {
      label: 'Single Model Audited',
      sublabel: 'Verifier Skipped',
      icon: 'shield',
      badgeClass: 'border-[#333333] bg-[#141414] text-[#a3a3a3] hover:border-[#444444]',
      iconColor: 'text-[#737373]',
      isActionable: Boolean(verification.cross_check_notes || verification.reason),
    }
  } else if (status === 'error') {
    badgeConfig = {
      label: 'Verifier Offline (Using Primary Findings)',
      icon: 'alert-triangle',
      badgeClass:
        'border-rose-600/40 bg-rose-950/20 text-rose-400 hover:border-rose-500/60',
      iconColor: 'text-rose-400',
      isActionable: Boolean(verification.error),
    }
  }

  const typeMeta = {
    false_positive: {
      label: 'FALSE POSITIVE',
      bg: 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300',
    },
    hallucination: {
      label: 'HALLUCINATION',
      bg: 'bg-purple-950/40 border-purple-500/40 text-purple-300',
    },
    missed_violation: {
      label: 'MISSED VIOLATION',
      bg: 'bg-rose-950/40 border-rose-500/40 text-rose-300',
    },
    value_mismatch: {
      label: 'VALUE MISMATCH',
      bg: 'bg-amber-950/40 border-amber-500/40 text-amber-300',
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
          <span className="opacity-80 text-[10px] bg-black/40 px-1.5 py-0.5 rounded border border-current/20">
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
          className="mt-3 p-4 bg-[#101010] border border-[#2a2a2a] rounded-sm text-xs space-y-4 shadow-xl"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#222222] pb-2.5">
            <div className="flex items-center gap-2 mono text-[11px] text-[#a3a3a3]">
              <span className="uppercase text-[#737373]">AUDITING ENGINE:</span>
              <span className="text-white font-medium">{modelName}</span>
              {confidence && (
                <>
                  <span className="text-[#444444]">|</span>
                  <span className="uppercase text-[#737373]">CONFIDENCE:</span>
                  <span className="text-white font-medium">{confidence}</span>
                </>
              )}
            </div>
            {verification.primary_violations_count !== undefined && (
              <div className="mono text-[10px] text-[#888888]">
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
            <div className="bg-[#151515] p-3 border-l-2 border-white/40 space-y-1">
              <div className="text-[10px] mono text-[#737373] uppercase tracking-wider font-semibold">
                AUDITOR CROSS-EXAMINATION NOTES
              </div>
              <p className="text-xs text-[#d4d4d4] leading-relaxed">
                {verification.cross_check_notes}
              </p>
            </div>
          )}

          {/* Reason or error message when skipped or failed */}
          {verification.reason && (
            <p className="text-xs text-[#888888] font-mono">
              Status info: {verification.reason}
            </p>
          )}
          {verification.error && (
            <div className="p-2.5 bg-rose-950/20 border border-rose-800/40 text-rose-300 text-xs font-mono">
              Verifier error details: {verification.error}
            </div>
          )}

          {/* Discrepancies listing */}
          {discrepancies.length > 0 && (
            <div className="space-y-3 pt-1">
              <div className="text-[10px] mono text-[#737373] uppercase tracking-wider font-bold">
                RECONCILED DISCREPANCIES ({discrepancies.length})
              </div>
              <div className="space-y-2.5">
                {discrepancies.map((d, idx) => {
                  const typeInfo = typeMeta[d.type] || {
                    label: d.type ? d.type.toUpperCase() : 'DISCREPANCY',
                    bg: 'bg-[#222222] border-[#444444] text-[#cccccc]',
                  }
                  return (
                    <div
                      key={idx}
                      className="p-3 bg-[#141414] border border-[#262626] rounded-sm space-y-2"
                    >
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="mono font-semibold text-white text-xs">
                          {d.rule_reference || 'Statutory Reference'}
                        </span>
                        <span
                          className={`text-[9px] mono px-2 py-0.5 border font-medium ${typeInfo.bg}`}
                        >
                          {typeInfo.label}
                        </span>
                      </div>
                      <p className="text-xs text-[#a3a3a3] leading-relaxed">
                        {d.description}
                      </p>
                      {(d.primary_finding || d.verifier_finding) && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                          <div className="p-2 bg-[#0d0d0d] border border-[#222222]">
                            <div className="text-[9px] text-[#737373] uppercase tracking-wider mb-0.5">
                              PRIMARY FINDING
                            </div>
                            <div className="text-[#a3a3a3]">
                              {d.primary_finding || 'None'}
                            </div>
                          </div>
                          <div className="p-2 bg-[#0d0d0d] border border-white/20">
                            <div className="text-[9px] text-white uppercase tracking-wider mb-0.5">
                              VERIFIER FINDING
                            </div>
                            <div className="text-white font-medium">
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
