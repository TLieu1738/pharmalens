import { ArrowRight, Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { EXAMPLE_PROMPTS } from '@/components/dashboard/examplePrompts'
import { buttonPrimary } from '@/components/ui/styles'

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
    <div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <div className="flex-1 rounded-lg border-2 border-accent-500/70 bg-white focus-within:border-accent-600">
          <label htmlFor="research-question" className="block px-4 pt-3.5 text-[15px] text-ink-900">
            What disease, drug or biological target would you like to investigate?
          </label>
          <textarea
            id="research-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit(e)
            }}
            maxLength={MAX_QUESTION_LENGTH}
            rows={3}
            placeholder="Ask a focused question to build a traceable, source-linked evidence review."
            className="block w-full resize-none border-0 bg-transparent px-4 pb-3 pt-2 text-sm leading-relaxed text-ink-900 placeholder:text-slate-500 focus:outline-none"
          />
          <p className="px-4 pb-2 text-right font-mono text-[11px] text-slate-400">
            {trimmed.length > 0 && trimmed.length < MIN_QUESTION_LENGTH ? `at least ${MIN_QUESTION_LENGTH} characters` : `${trimmed.length}/${MAX_QUESTION_LENGTH}`}
          </p>
        </div>
        <button type="submit" disabled={!valid || submitting} className={`${buttonPrimary} py-3 lg:mt-6 lg:w-44`}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
          Start research
          {!submitting && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
        </button>
      </form>
      {error && (
        <p role="alert" className="mt-2 text-sm text-rose-700">
          {error}
        </p>
      )}
      <p className="mt-4 text-[13px] text-slate-600">Try a research question</p>
      <div className="mt-2 grid gap-3 md:grid-cols-3">
        {EXAMPLE_PROMPTS.map((ex) => (
          <button
            key={ex.label}
            type="button"
            onClick={() => setQuestion(ex.prompt)}
            className="truncate rounded-md border border-slate-200 bg-white px-3 py-2 text-left text-[13px] text-accent-700 transition-colors hover:border-accent-500"
          >
            {ex.label}
          </button>
        ))}
      </div>
    </div>
  )
}
