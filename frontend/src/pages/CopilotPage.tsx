import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Bot, CornerDownLeft, FileText, LoaderCircle, MessageCircle, Send, Sparkles, UserRound } from 'lucide-react'
import { getApiError } from '../api/client'
import { workspaceApi } from '../api/workspace'
import type { ChatSource } from '../types/api'

interface ChatMessage { id: string; role: 'user' | 'assistant'; content: string; sources?: ChatSource[] }

export function CopilotPage() {
  const [question, setQuestion] = useState('')
  const [conversationId, setConversationId] = useState<string | undefined>()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const scrollArea = useRef<HTMLDivElement>(null)
  const send = useMutation({
    mutationFn: (prompt: string) => workspaceApi.chat(prompt, conversationId),
    onMutate: prompt => {
      setErrorMessage(null)
      setMessages(current => [...current, { id: `user-${Date.now()}`, role: 'user', content: prompt }])
    },
    onSuccess: response => {
      setConversationId(response.conversation_id)
      setMessages(current => [...current, { id: `assistant-${Date.now()}`, role: 'assistant', content: response.answer, sources: response.sources }])
    },
    onError: error => setErrorMessage(getApiError(error, 'The AI Co-Pilot could not respond. Please try again.')),
  })
  useEffect(() => {
    const area = scrollArea.current
    if (area && typeof area.scrollTo === 'function') area.scrollTo({ top: area.scrollHeight, behavior: 'smooth' })
  }, [messages, send.isPending, errorMessage])
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || send.isPending) return
    setQuestion('')
    send.mutate(trimmed)
  }
  return <div className="mx-auto flex min-h-[calc(100vh-150px)] max-w-5xl flex-col">
    <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[#f0f1ff] text-brand"><Sparkles size={19} /></span><div><p className="text-xs font-medium text-muted">Employee workspace</p><h1 className="mt-1 text-xl font-semibold">AI Co-Pilot</h1></div></div>
    <div className="mt-5 flex items-start gap-2 rounded-lg border border-[#e7e8ff] bg-[#f4f5ff] px-3.5 py-3 text-[11px] leading-relaxed text-[#555eaa]"><MessageCircle size={14} className="mt-0.5 shrink-0" /><p>Ask questions about your indexed TaskFlow documents. This conversation is held in this page only and is not saved as chat history.</p></div>
    <section ref={scrollArea} aria-live="polite" className="mt-5 flex-1 space-y-5 overflow-y-auto rounded-xl border border-line bg-white p-4 shadow-card sm:p-6">
      {messages.length === 0 && <div className="grid min-h-64 content-center justify-items-center px-3 text-center"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-[#f0f1ff] text-brand"><Bot size={23} /></span><h2 className="mt-4 text-sm font-semibold">What can I help you find?</h2><p className="mt-1 max-w-sm text-xs leading-relaxed text-muted">Ask a question about project processes, policies, or other indexed documents. Answers include source references when available.</p><div className="mt-5 flex flex-wrap justify-center gap-2">{['Where can I find the project planning guide?', 'What does the documentation say about task dependencies?'].map(prompt => <button key={prompt} onClick={() => setQuestion(prompt)} className="rounded-full border border-line px-3 py-2 text-[10px] text-muted transition hover:border-brand hover:text-brand">{prompt}</button>)}</div></div>}
      {messages.map(message => <article key={message.id} className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}><span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${message.role === 'user' ? 'bg-[#e8ebff] text-brand' : 'bg-gray-100 text-gray-600'}`}>{message.role === 'user' ? <UserRound size={15} /> : <Bot size={15} />}</span><div className={`max-w-[88%] min-w-0 rounded-xl px-4 py-3 ${message.role === 'user' ? 'bg-brand text-white' : 'bg-[#f8f9fb] text-ink'}`}><p className="whitespace-pre-wrap text-xs leading-6">{message.content}</p>{message.role === 'assistant' && message.sources && <div className="mt-3 border-t border-line pt-3">{message.sources.length === 0 ? <p className="text-[10px] text-amber-800">No matching source documents were retrieved, so the available context may be insufficient.</p> : <><p className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold text-muted"><FileText size={12} /> Sources</p><div className="space-y-2">{message.sources.map((source, index) => <details key={`${source.source}-${index}`} className="rounded-lg border border-line bg-white p-2.5"><summary className="cursor-pointer text-[10px] font-medium text-brand">{source.source} <span className="ml-1 text-muted">{Math.round(source.relevance_score * 100)}% relevant</span></summary><p className="mt-2 whitespace-pre-wrap text-[10px] leading-relaxed text-muted">{source.content}</p></details>)}</div></>}</div>}</div></article>)}
      {send.isPending && <div className="flex items-center gap-3 text-xs text-muted"><span className="grid h-8 w-8 place-items-center rounded-full bg-gray-100"><Bot size={15} /></span><LoaderCircle size={14} className="animate-spin" /> Searching indexed documents…</div>}
      {errorMessage && <div role="alert" className="ml-11 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-700">{errorMessage}</div>}
    </section>
    <form onSubmit={submit} className="mt-3 rounded-xl border border-line bg-white p-2 shadow-card"><label htmlFor="copilot-question" className="sr-only">Ask the AI Co-Pilot</label><div className="flex items-end gap-2"><textarea id="copilot-question" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} maxLength={4000} rows={2} placeholder="Ask a question about your documents…" className="max-h-36 min-h-12 flex-1 resize-y bg-transparent px-3 py-2 text-xs leading-5 outline-none placeholder:text-muted" /><button disabled={!question.trim() || send.isPending} aria-label="Send question" className="mb-1 grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand text-white transition hover:bg-[#424dd5] disabled:cursor-not-allowed disabled:opacity-50">{send.isPending ? <LoaderCircle size={15} className="animate-spin" /> : <Send size={15} />}</button></div><div className="flex items-center justify-between px-3 pb-1 text-[9px] text-muted"><span><CornerDownLeft size={10} className="mr-1 inline" />Enter to send · Shift+Enter for a new line</span><span>{question.length}/4000</span></div></form>
  </div>
}
