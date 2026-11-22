import { ArrowRight, Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { EXAMPLE_PROMPTS } from '@/components/dashboard/examplePrompts'

export const MIN_QUESTION_LENGTH = 20
export const MAX_QUESTION_LENGTH = 2000

interface Props {
  onSubmit: (question: string) => void
  submitting: boolean
  error: string | null
}

export function ResearchQuestionForm({ onSubmit, submitting, error }: Props) {
  const [question, setQuestion] = useState('')
  const trimmed = question.trim()
  const valid = trimmed.length >= MIN_QUESTION_LENGTH && trimmed.length <= MAX_QUESTION_LENGTH

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (valid && !submitting) onSubmit(trimmed)
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-slate-200 bg-white shadow-sm focus-within:border-accent-500">
      <label htmlFor="research-question" className="sr-only">
        Research question
      </label>
      <textarea
        id="research-question"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit(e)
        }}
        maxLength={MAX_QUESTION_LENGTH}
        rows={5}
        placeholder="Describe the disease area, targets, compounds or questions you want investigated…"
        className="block w-full resize-none rounded-t-lg border-0 px-4 py-3.5 text-[15px] leading-relaxed text-ink-900 placeholder:text-slate-400 focus:outline-none"
      />
      <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 px-4 py-3">
        <span className="mr-1 text-xs text-slate-500">Try:</span>
        {EXAMPLE_PROMPTS.map((ex) => (
          <button
            key={ex.label}
            type="button"
            onClick={() => setQuestion(ex.prompt)}
            className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 transition-colors hover:border-accent-500 hover:text-accent-700"
          >
            {ex.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-3">
          <span className="font-mono text-[11px] text-slate-400">
            {trimmed.length < MIN_QUESTION_LENGTH && trimmed.length > 0 ? `min ${MIN_QUESTION_LENGTH} chars` : `${trimmed.length}/${MAX_QUESTION_LENGTH}`}
          </span>
          <button
            type="submit"
            disabled={!valid || submitting}
            className="inline-flex items-center gap-1.5 rounded-md bg-ink-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-ink-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
            Start research
            {!submitting && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="rounded-b-lg border-t border-rose-100 bg-rose-50 px-4 py-2 text-xs text-rose-700">
          {error}
        </p>
      )}
    </form>
  )
}
