"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { getIngestion, approveIngestion, rejectIngestion } from "@/lib/api"
import { Ingestion, ExtractedRule, ExtractedProgram } from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Card, CardContent } from "@/components/ui/card"
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table"
import {
  Dialog, DialogContent, DialogHeader,
  DialogTitle, DialogDescription,
} from "@/components/ui/dialog"
import { toast } from "sonner"
import {
  ArrowLeft, RefreshCw, AlertCircle,
  CheckCircle2, XCircle, Loader2, FileText,
} from "lucide-react"

// ─── Constants ────────────────────────────────────────────────────────────────

const POLL_INTERVAL = 3000 // ms
const POLL_MAX      = 60   // attempts (~3 min)

// ─── Editable rule row ────────────────────────────────────────────────────────

function RuleRow({
  rule, index, onChange,
}: {
  rule:     ExtractedRule
  index:    number
  onChange: (i: number, updated: ExtractedRule) => void
}) {
  function set<K extends keyof ExtractedRule>(k: K, v: ExtractedRule[K]) {
    onChange(index, { ...rule, [k]: v })
  }

  return (
    <TableRow>
      <TableCell className="font-mono text-xs text-gray-500 whitespace-nowrap">
        {rule.rule_type.replace(/_/g, " ")}
      </TableCell>
      <TableCell className="text-gray-500 text-sm">{rule.operator}</TableCell>
      <TableCell>
        <Input
          className="h-7 w-28 text-sm"
          value={rule.value}
          onChange={e => set("value", e.target.value)}
        />
      </TableCell>
      <TableCell>
        <Input
          className="h-7 text-sm"
          value={rule.description ?? ""}
          placeholder="Add description…"
          onChange={e => set("description", e.target.value)}
        />
      </TableCell>
      <TableCell className="text-gray-500 text-sm">
        {rule.applies_to_industry ?? <span className="text-gray-300">All</span>}
      </TableCell>
      <TableCell>
        <Switch
          checked={rule.is_hard_stop}
          onCheckedChange={v => set("is_hard_stop", v)}
        />
      </TableCell>
      <TableCell className="text-xs text-gray-400 max-w-xs truncate italic">
        {rule.source_quote ?? "—"}
      </TableCell>
    </TableRow>
  )
}

// ─── Programs table (read-only) ───────────────────────────────────────────────

function ProgramsTable({ programs }: { programs: ExtractedProgram[] }) {
  if (!programs.length) return (
    <p className="text-sm text-gray-400 italic py-4">No programs extracted.</p>
  )
  return (
    <div className="border rounded-lg overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-gray-50">
            <TableHead>Name</TableHead>
            <TableHead>Min Amount</TableHead>
            <TableHead>Max Amount</TableHead>
            <TableHead>Credit Tier</TableHead>
            <TableHead>Description</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {programs.map((p, i) => (
            <TableRow key={i}>
              <TableCell className="font-medium text-gray-900">{p.name}</TableCell>
              <TableCell className="text-gray-600">
                {p.min_amount != null ? `$${p.min_amount.toLocaleString()}` : "—"}
              </TableCell>
              <TableCell className="text-gray-600">
                {p.max_amount != null ? `$${p.max_amount.toLocaleString()}` : "—"}
              </TableCell>
              <TableCell>
                {p.credit_tier
                  ? <Badge className="bg-blue-50 text-blue-700 border-blue-200">{p.credit_tier}</Badge>
                  : <span className="text-gray-400">—</span>}
              </TableCell>
              <TableCell className="text-gray-500 text-sm">{p.description ?? "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

// ─── Polling indicator ────────────────────────────────────────────────────────

function PollingState({ attempts }: { attempts: number }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4 border rounded-lg text-gray-400">
      <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
      <div className="text-center">
        <p className="text-sm font-medium text-gray-600">Extracting PDF with GPT-4o…</p>
        <p className="text-xs text-gray-400 mt-1">
          This usually takes 15–30 seconds. Checking every 3s
          {attempts > 1 ? ` (attempt ${attempts})` : ""}…
        </p>
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function IngestDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router  = useRouter()

  const [ingestion, setIngestion]   = useState<Ingestion | null>(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)
  const [polling, setPolling]       = useState(false)
  const [pollAttempts, setPollAttempts] = useState(0)
  const [tab, setTab]               = useState<"rules" | "programs">("rules")

  // Editable copies of extracted data
  const [rules, setRules]       = useState<ExtractedRule[]>([])
  const [programs, setPrograms] = useState<ExtractedProgram[]>([])

  // Action states
  const [approving, setApproving] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [confirmReject, setConfirmReject] = useState(false)

  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Load ────────────────────────────────────────────────────────────────────

  const load = useCallback(async (isPolling = false) => {
    try {
      if (!isPolling) { setLoading(true); setError(null) }
      const data = await getIngestion(Number(id))
      setIngestion(data)

      if (data.extracted) {
        setRules(data.extracted.rules ?? [])
        setPrograms(data.extracted.programs ?? [])
        setPolling(false)
      }
      return data
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to load ingestion.")
      setPolling(false)
      return null
    } finally {
      if (!isPolling) setLoading(false)
    }
  }, [id])

  // ── Auto-poll until extracted ───────────────────────────────────────────────

  useEffect(() => {
    let attempts = 0

    async function tick() {
      attempts++
      setPollAttempts(attempts)
      const data = await load(attempts > 1)

      if (!data?.extracted && attempts < POLL_MAX) {
        setPolling(true)
        pollRef.current = setTimeout(tick, POLL_INTERVAL)
      } else if (attempts >= POLL_MAX) {
        setPolling(false)
        toast.error("Extraction timed out. Please refresh manually.")
      }
    }

    tick()
    return () => { if (pollRef.current) clearTimeout(pollRef.current) }
  }, [load])

  // ── Rule editing ────────────────────────────────────────────────────────────

  function updateRule(i: number, updated: ExtractedRule) {
    setRules(rs => rs.map((r, idx) => idx === i ? updated : r))
  }

  // ── Approve ─────────────────────────────────────────────────────────────────

  async function handleApprove() {
    setApproving(true)
    try {
      await approveIngestion(Number(id), {
        rules,
        programs,
        lender_name:   ingestion?.extracted?.lender_name,
        contact_name:  ingestion?.extracted?.contact_name,
        contact_email: ingestion?.extracted?.contact_email,
        contact_phone: ingestion?.extracted?.contact_phone,
      })
      toast.success("Lender approved and added to the matching engine.")
      router.push("/lenders")
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? "Approval failed.")
      setApproving(false)
    }
  }

  // ── Reject ──────────────────────────────────────────────────────────────────

  async function handleReject() {
    setRejecting(true)
    try {
      await rejectIngestion(Number(id))
      toast.success("Ingestion rejected.")
      router.push("/ingest")
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? "Rejection failed.")
      setRejecting(false)
    } finally {
      setConfirmReject(false)
    }
  }

  // ── States ──────────────────────────────────────────────────────────────────

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-400">
      <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading…
    </div>
  )

  if (error || !ingestion) return (
    <div className="flex flex-col items-center justify-center h-64 gap-4 text-gray-500">
      <AlertCircle className="w-8 h-8 text-red-400" />
      <p>{error ?? "Ingestion not found."}</p>
      <Button variant="outline" onClick={() => router.push("/ingest")}>Back</Button>
    </div>
  )

  const isSettled  = ingestion.status === "APPROVED" || ingestion.status === "REJECTED"
  const isExtracted = !!ingestion.extracted

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => router.push("/ingest")}
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-gray-600 mb-2 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back to ingestions
          </button>
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-gray-400" />
            <h1 className="text-xl font-bold text-gray-900">{ingestion.filename}</h1>
            {ingestion.status === "APPROVED" && (
              <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">Approved</Badge>
            )}
            {ingestion.status === "REJECTED" && (
              <Badge className="bg-red-100 text-red-700 border-red-200">Rejected</Badge>
            )}
            {ingestion.status === "PENDING_REVIEW" && (
              <Badge className="bg-amber-100 text-amber-700 border-amber-200">Pending Review</Badge>
            )}
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Ingestion #{ingestion.id} · Uploaded{" "}
            {new Date(ingestion.created_at).toLocaleDateString("en-US", {
              month: "short", day: "numeric", year: "numeric",
            })}
          </p>
        </div>

        {/* Approve / Reject — only when pending and extracted */}
        {!isSettled && isExtracted && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600"
              onClick={() => setConfirmReject(true)}
              disabled={rejecting || approving}
            >
              <XCircle className="w-4 h-4 mr-1.5" /> Reject
            </Button>
            <Button
              onClick={handleApprove}
              disabled={approving || rejecting}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {approving
                ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                : <CheckCircle2 className="w-4 h-4 mr-1.5" />}
              Approve & Add Lender
            </Button>
          </div>
        )}
      </div>

      {/* Lender meta */}
      {isExtracted && (
        <Card>
          <CardContent className="pt-5 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            {[
              { label: "Lender Name",  value: ingestion.extracted!.lender_name },
              { label: "Contact",      value: ingestion.extracted!.contact_name },
              { label: "Email",        value: ingestion.extracted!.contact_email },
              { label: "Phone",        value: ingestion.extracted!.contact_phone },
            ].map(({ label, value }) => (
              <div key={label}>
                <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">{label}</p>
                <p className="font-medium text-gray-800">{value ?? "—"}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Extraction notes */}
      {ingestion.extracted?.extraction_notes && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          <span className="font-medium">Extraction notes: </span>
          {ingestion.extracted.extraction_notes}
        </div>
      )}

      {/* Error message */}
      {ingestion.error_message && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <span className="font-medium">Error: </span>{ingestion.error_message}
        </div>
      )}

      {/* Polling / extraction pending */}
      {!isExtracted && polling && <PollingState attempts={pollAttempts} />}

      {/* Extracted content */}
      {isExtracted && (
        <div className="space-y-4">

          {/* Settled notice */}
          {isSettled && (
            <div className={`p-3 rounded-lg text-sm border ${
              ingestion.status === "APPROVED"
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-red-50 border-red-200 text-red-800"
            }`}>
              This ingestion has been <strong>{ingestion.status.toLowerCase()}</strong> and is read-only.
              {ingestion.status === "APPROVED" && (
                <button
                  className="ml-2 underline"
                  onClick={() => ingestion.lender_id && router.push(`/lenders/${ingestion.lender_id}`)}
                >
                  View lender →
                </button>
              )}
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-1 border-b">
            {(["rules", "programs"] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
                  tab === t
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                {t}
                <span className="ml-1.5 text-xs text-gray-400">
                  ({t === "rules" ? rules.length : programs.length})
                </span>
              </button>
            ))}
          </div>

          {/* Rules tab */}
          {tab === "rules" && (
            rules.length === 0 ? (
              <p className="text-sm text-gray-400 italic py-4">No rules extracted.</p>
            ) : (
              <div className="border rounded-lg overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-50">
                      <TableHead className="whitespace-nowrap">Rule Type</TableHead>
                      <TableHead>Operator</TableHead>
                      <TableHead>Value</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Industry Scope</TableHead>
                      <TableHead className="whitespace-nowrap">Hard Stop</TableHead>
                      <TableHead>Source Quote</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rules.map((rule, i) => (
                      isSettled
                        // Read-only when approved/rejected
                        ? (
                          <TableRow key={i}>
                            <TableCell className="font-mono text-xs text-gray-500 whitespace-nowrap">
                              {rule.rule_type.replace(/_/g, " ")}
                            </TableCell>
                            <TableCell className="text-gray-500 text-sm">{rule.operator}</TableCell>
                            <TableCell className="text-gray-700 font-medium">{rule.value}</TableCell>
                            <TableCell className="text-gray-500 text-sm">{rule.description ?? "—"}</TableCell>
                            <TableCell className="text-gray-500 text-sm">
                              {rule.applies_to_industry ?? <span className="text-gray-300">All</span>}
                            </TableCell>
                            <TableCell>
                              {rule.is_hard_stop
                                ? <Badge className="bg-red-50 text-red-600 border-red-200">Yes</Badge>
                                : <span className="text-gray-400 text-sm">No</span>}
                            </TableCell>
                            <TableCell className="text-xs text-gray-400 italic max-w-xs truncate">
                              {rule.source_quote ?? "—"}
                            </TableCell>
                          </TableRow>
                        )
                        : (
                          <RuleRow key={i} rule={rule} index={i} onChange={updateRule} />
                        )
                    ))}
                  </TableBody>
                </Table>
              </div>
            )
          )}

          {/* Programs tab */}
          {tab === "programs" && <ProgramsTable programs={programs} />}
        </div>
      )}

      {/* Reject confirm dialog */}
      <Dialog open={confirmReject} onOpenChange={setConfirmReject}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject this ingestion?</DialogTitle>
            <DialogDescription>
              The extracted rules and programs will be discarded and no lender will be created.
              This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3 mt-2">
            <Button variant="outline" onClick={() => setConfirmReject(false)}>Cancel</Button>
            <Button variant="destructive" disabled={rejecting} onClick={handleReject}>
              {rejecting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Reject"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

    </div>
  )
}