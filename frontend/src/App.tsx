import { useEffect, useState, type FormEvent } from 'react'
import './App.css'

type ResearchPlan = {
  sub_questions: string[]
  scope_boundaries: string[]
  recommended_source_types: string[]
}

type EvidenceRecord = {
  evidence_id: string
  query: string
  source_url: string
  source_title: string
  retrieved_at: string
  passage: string
  source_type: string
}

type ResearchClaim = {
  claim_id: string
  claim_text: string
  evidence_ids: string[]
  status: string
}

type VerifiedClaim = {
  claim: ResearchClaim
  verification: {
    claim_id: string
    verdict: 'supported' | 'contradicted' | 'insufficient_evidence'
    rationale: string
    evidence_ids: string[]
    checked_at: string
  }
}

type ResearchReport = {
  answer: string
  sections: {
    heading: string
    body: string
    evidence_ids: string[]
  }[]
}

type ResearchRunResult = {
  question: string
  report: ResearchReport | null
  plan: ResearchPlan
  evidence: EvidenceRecord[]
  claims: ResearchClaim[]
  verifications: VerifiedClaim[]
}

type ResearchJobStatus = {
  run_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  current_stage: string | null
  error: string | null
  created_at: string
  updated_at: string
  result: ResearchRunResult | null
}

type AcceptedRun = {
  run_id: string
}

class UserFacingError extends Error {}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
const POLL_INTERVAL_MS = 2500

function httpErrorMessage(status: number): string {
  if (status === 400 || status === 422) {
    return 'Please check your research question and settings, then try again.'
  }
  if (status === 404) {
    return 'This research run could not be found. Start a new research run.'
  }
  if (status === 429) {
    return 'DeepDive is receiving too many requests. Wait a moment, then try again.'
  }
  if (status === 502) {
    return 'A connected provider could not complete the request. Please try again later.'
  }
  if (status === 503) {
    return 'Research is temporarily unavailable because a provider is not ready.'
  }
  if (status >= 500) {
    return 'DeepDive encountered a server issue. Please try again later.'
  }
  return 'The request could not be completed. Please try again.'
}

function jobErrorMessage(error: string | null): string {
  const normalizedError = error?.toLowerCase() || ''
  if (
    normalizedError.includes('insufficient credits') ||
    normalizedError.includes('payment required')
  ) {
    return 'The AI provider account has insufficient credits for this request. Add credits to the provider account or select a model available within your current balance.'
  }
  if (
    normalizedError.includes('quota') ||
    normalizedError.includes('rate limit') ||
    normalizedError.includes('resource_exhausted') ||
    normalizedError.includes('429')
  ) {
    return 'A connected provider has reached its request quota. Check its usage or rate-limit dashboard, then retry after the quota window resets.'
  }
  if (
    normalizedError.includes('configuration') ||
    normalizedError.includes('credentials') ||
    normalizedError.includes('api key')
  ) {
    return 'The research service is not fully configured. Check the provider and API-key settings on the server.'
  }
  if (
    normalizedError.includes('model') &&
    (normalizedError.includes('text answer') || normalizedError.includes('without returning text'))
  ) {
    return 'The selected AI model did not return a text answer. Choose a currently available text/chat model and try again.'
  }
  if (normalizedError.includes('search provider') || normalizedError.includes('web search')) {
    return 'The web search provider could not complete the request. Please try again later.'
  }
  return 'Research could not be completed. Please try again later. If the problem continues, check provider status and server logs.'
}

function connectionErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof UserFacingError) return error.message
  if (error instanceof TypeError) {
    return 'Could not connect to DeepDive. Check that the API is running and your connection is available.'
  }
  return fallback
}

function App() {
  const [question, setQuestion] = useState('')
  const [resultsPerQuery, setResultsPerQuery] = useState(3)
  const [run, setRun] = useState<AcceptedRun | null>(null)
  const [job, setJob] = useState<ResearchJobStatus | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!run) return

    let cancelled = false
    let timeout: number | undefined
    const controller = new AbortController()

    const poll = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/research/runs/${encodeURIComponent(run.run_id)}`,
          { signal: controller.signal },
        )
        if (!response.ok) throw new UserFacingError(httpErrorMessage(response.status))

        const status = (await response.json()) as ResearchJobStatus
        if (cancelled) return
        setJob(status)
        if (status.status === 'failed') {
          setError(jobErrorMessage(status.error))
          return
        }
        if (status.status !== 'completed') {
          timeout = window.setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch (pollError) {
        if (!cancelled && !(pollError instanceof DOMException && pollError.name === 'AbortError')) {
          setError(connectionErrorMessage(
            pollError,
            'Unable to check the research run status. Please try again.',
          ))
        }
      }
    }

    void poll()
    return () => {
      cancelled = true
      controller.abort()
      if (timeout !== undefined) window.clearTimeout(timeout)
    }
  }, [run])

  async function startResearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedQuestion = question.trim()
    if (!normalizedQuestion || submitting) return

    setSubmitting(true)
    setError(null)
    setRun(null)
    setJob(null)

    try {
      const response = await fetch(`${API_BASE}/research/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: normalizedQuestion,
          results_per_query: resultsPerQuery,
        }),
      })
      if (!response.ok) throw new UserFacingError(httpErrorMessage(response.status))
      const accepted = (await response.json()) as AcceptedRun
      setRun(accepted)
      setJob({
        run_id: accepted.run_id,
        status: 'queued',
        current_stage: 'Waiting to start',
        error: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        result: null,
      })
    } catch (submitError) {
      setError(connectionErrorMessage(
        submitError,
        'Unable to start research. Please try again.',
      ))
    } finally {
      setSubmitting(false)
    }
  }

  const result = job?.status === 'completed' ? job.result : null
  const verificationByClaim = new Map(
    result?.verifications.map((item) => [item.claim.claim_id, item.verification]) ?? [],
  )

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="DeepDive home">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <path d="M5 7.5h10.5a9 9 0 1 1 0 18H5v-18Z" />
              <path d="M12 13h5a3.5 3.5 0 1 1 0 7h-5v-7Z" />
              <circle cx="23.5" cy="8.5" r="2" />
            </svg>
          </span>
          <span>deepdive<span className="brand-period">.</span></span>
        </a>
        <div className="topbar-note"><span className="online-dot" /> Research workspace</div>
      </header>

      <main>
        <section className="hero">
          <div className="eyebrow"><span className="eyebrow-line" /> EVIDENCE-FIRST RESEARCH</div>
          <h1>Go beyond the<br /><span>surface answer.</span></h1>
          <p className="hero-copy">
            Ask a question. DeepDive breaks it down, searches the web, and checks
            each finding against its sources.
          </p>

          <form className="research-form" onSubmit={startResearch}>
            <label className="visually-hidden" htmlFor="research-question">
              What would you like to research?
            </label>
            <textarea
              id="research-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What would you like to research?"
              rows={3}
              maxLength={2000}
              required
              disabled={submitting || job?.status === 'queued' || job?.status === 'running'}
            />
            <div className="form-footer">
              <label className="results-control">
                <span>Sources per question</span>
                <select
                  value={resultsPerQuery}
                  onChange={(event) => setResultsPerQuery(Number(event.target.value))}
                  disabled={submitting || job?.status === 'queued' || job?.status === 'running'}
                >
                  {[1, 2, 3, 4, 5].map((count) => (
                    <option key={count} value={count}>{count}</option>
                  ))}
                </select>
              </label>
              <button
                className="research-button"
                type="submit"
                disabled={
                  submitting ||
                  !question.trim() ||
                  job?.status === 'queued' ||
                  job?.status === 'running'
                }
              >
                {submitting ? 'Starting…' : 'Start research'}
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M4 10h11M10 5l5 5-5 5" />
                </svg>
              </button>
            </div>
          </form>

          <div className="workflow-hint" aria-label="Research workflow">
            <span>PLAN</span><i />
            <span>SEARCH</span><i />
            <span>VERIFY</span><i />
            <span>SYNTHESIZE</span><i />
            <span>ANSWER</span>
          </div>
        </section>

        {error && (
          <div className="alert error-alert" role="alert">
            <span className="alert-icon">!</span>
            <div>
              <strong>{job?.status === 'failed' ? 'Research couldn’t finish' : 'Request couldn’t be completed'}</strong>
              <p>{error}</p>
            </div>
            {job?.status === 'failed' && (
              <button
                className="text-button"
                type="button"
                onClick={() => { setRun(null); setJob(null); setError(null) }}
              >
                Start over
              </button>
            )}
          </div>
        )}

        {job && (
          <section className="run-panel" aria-live="polite">
            <div className="run-heading">
              <div>
                <div className="section-kicker">RESEARCH RUN</div>
                <h2>{job.status === 'completed' ? 'Research complete' : 'Working on your research'}</h2>
              </div>
              <span className={`status-pill status-${job.status}`}>
                {job.status === 'running' || job.status === 'queued' ? <span className="status-spinner" /> : null}
                {job.status}
              </span>
            </div>
            <p className="run-stage">
              {job.status === 'completed'
                ? 'Your findings and source checks are ready.'
                : job.current_stage || 'Waiting for progress…'}
            </p>
            {(job.status === 'queued' || job.status === 'running') && (
              <div className="progress-track"><span /></div>
            )}
          </section>
        )}

        {result && (
          <section className="results" aria-label="Research results">
            <div className="results-summary">
              <div className="section-kicker">{result.report ? 'RESEARCH ANSWER' : 'RESEARCH RUN'}</div>
              <h2>{result.question}</h2>
              {result.report
                ? <p className="report-answer">{result.report.answer}</p>
                : <p className="report-unavailable">This run was completed before research summaries were added. Open the research trail to review its findings.</p>}
            </div>

            {result.report && <div className="report-sections">
              {result.report.sections.map((section) => (
                <article className="report-section" key={section.heading}>
                  <h3>{section.heading}</h3>
                  <p>{section.body}</p>
                  {section.evidence_ids.length > 0 && (
                    <div className="report-citations" aria-label="Sources for this section">
                      <span>Sources</span>
                      {section.evidence_ids.map((id) => {
                        const source = result.evidence.find((item) => item.evidence_id === id)
                        return source ? (
                          <a
                            key={id}
                            href={source.source_url}
                            target="_blank"
                            rel="noreferrer"
                            title={source.source_title}
                          >
                            {id} ↗
                          </a>
                        ) : null
                      })}
                    </div>
                  )}
                </article>
              ))}
            </div>}
            {result.report && <p className="disclaimer">
              This AI-generated report is grounded in search snippets and
              verified claim assessments. Review the cited sources directly;
              verification is not independent proof of factual truth.
            </p>}

            <details className="research-trail">
              <summary>
                Research trail
                <span>
                  {result.plan.sub_questions.length} angles · {result.evidence.length} sources · {result.claims.length} claims checked
                </span>
              </summary>

              <section className="result-section">
                <div className="section-title">
                  <span className="section-number">01</span>
                  <div><div className="section-kicker">RESEARCH PLAN</div><h3>Questions explored</h3></div>
                </div>
                <ol className="question-list">
                  {result.plan.sub_questions.map((item) => <li key={item}>{item}</li>)}
                </ol>
                <div className="meta-columns">
                  <div><h4>Scope boundaries</h4><ul>{result.plan.scope_boundaries.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  <div><h4>Suggested source types</h4><ul>{result.plan.recommended_source_types.map((item) => <li key={item}>{item}</li>)}</ul></div>
                </div>
              </section>

              <section className="result-section">
                <div className="section-title">
                  <span className="section-number">02</span>
                  <div><div className="section-kicker">SOURCE MATERIAL</div><h3>Evidence collected</h3></div>
                </div>
                <div className="evidence-grid">
                  {result.evidence.map((item) => (
                    <article className="evidence-card" key={item.evidence_id}>
                      <div className="evidence-meta"><span>{item.evidence_id}</span><span>{item.source_type.replace('_', ' ')}</span></div>
                      <h4><a href={item.source_url} target="_blank" rel="noreferrer">{item.source_title}<span aria-hidden="true"> ↗</span></a></h4>
                      <p>{item.passage}</p>
                      <div className="evidence-query">Found for: {item.query}</div>
                    </article>
                  ))}
                </div>
              </section>

              <section className="result-section">
                <div className="section-title">
                  <span className="section-number">03</span>
                  <div><div className="section-kicker">CLAIM CHECK</div><h3>What the evidence supports</h3></div>
                </div>
                <div className="claim-list">
                  {result.claims.map((claim) => {
                    const verification = verificationByClaim.get(claim.claim_id)
                    const verdict = verification?.verdict ?? claim.status
                    return (
                      <article className="claim-card" key={claim.claim_id}>
                        <div className="claim-topline">
                          <span className={`verdict verdict-${verdict.replaceAll('_', '-')}`}>
                            <span className="verdict-dot" />{verdict.replaceAll('_', ' ')}
                          </span>
                          <span className="claim-id">{claim.claim_id}</span>
                        </div>
                        <p className="claim-text">{claim.claim_text}</p>
                        {verification && <p className="claim-rationale">{verification.rationale}</p>}
                        <div className="citation-row">
                          <span>Evidence</span>
                          {claim.evidence_ids.length
                            ? claim.evidence_ids.map((id) => {
                              const source = result.evidence.find((item) => item.evidence_id === id)
                              return source ? (
                                <a key={id} href={source.source_url} target="_blank" rel="noreferrer" title={source.source_title}>{id} ↗</a>
                              ) : <span key={id}>{id}</span>
                            })
                            : <em>No evidence cited</em>}
                        </div>
                      </article>
                    )
                  })}
                </div>
              </section>
            </details>
          </section>
        )}
      </main>

      <footer className="footer">
        <a className="brand footer-brand" href="/" aria-label="DeepDive home">
          <span>deepdive<span className="brand-period">.</span></span>
        </a>
        <span>Research with receipts.</span>
      </footer>
    </div>
  )
}

export default App
