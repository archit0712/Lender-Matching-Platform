"use client"

import { useEffect, useState } from "react"
import { useRouter, useParams } from "next/navigation"
import { getLender, updateRule, deleteRule } from "@/lib/api"
import { Lender, PolicyRule, LenderProgram } from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
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
  Save, Trash2, Eye, EyeOff,
} from "lucide-react"

// ─── Types ────────────────────────────────────────────────────────────────────

interface RowEdit {
  value:        string
  description:  string
  is_hard_stop: boolean
  is_active:    boolean
}

// ─── Rule row ─────────────────────────────────────────────────────────────────

function RuleRow({
  rule,
  onSave,
  onDelete,
}: {
  rule:     PolicyRule
  onSave:   (id: number, data: RowEdit) => Promise<void>
  onDelete: (id: number) => void
}) {
  const [edit, setEdit]       = useState<RowEdit>({
    value:        rule.value,
    description:  rule.description ?? "",
    is_hard_stop: rule.is_hard_stop,
    is_active:    rule.is_active,
  })
  const [saving, setSaving]   = useState(false)
  const [dirty, setDirty]     = useState(false)

  function set<K extends keyof RowEdit>(k: K, v: RowEdit[K]) {
    setEdit(e => ({ ...e, [k]: v }))
    setDirty(true)
  }

  async function save() {
    setSaving(true)
    try {
      await onSave(rule.id, edit)
      setDirty(false)
      toast.success("Rule saved.")
    } catch {
      toast.error("Failed to save rule.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <TableRow className={!edit.is_active ? "opacity-50" : ""}>
      {/* Rule type */}
      <TableCell className="font-mono text-xs text-gray-500 whitespace-nowrap">
        {rule.rule_type.replace(/_/g, " ")}
      </TableCell>

      {/* Operator */}
      <TableCell className="text-gray-500 text-sm">{rule.operator}</TableCell>

      {/* Value — editable */}
      <TableCell>
        <Input
          className="h-7 w-28 text-sm"
          value={edit.value}
          onChange={e => set("value", e.target.value)}
        />
      </TableCell>

      {/* Description — editable */}
      <TableCell>
        <Input
          className="h-7 text-sm"
          value={edit.description}
          placeholder="Add description…"
          onChange={e => set("description", e.target.value)}
        />
      </TableCell>

      {/* Industry scope */}
      <TableCell className="text-gray-500 text-sm">
        {rule.applies_to_industry ?? <span className="text-gray-300">All</span>}
      </TableCell>

      {/* Hard stop toggle */}
      <TableCell>
        <Switch
          checked={edit.is_hard_stop}
          onCheckedChange={v => set("is_hard_stop", v)}
        />
      </TableCell>

      {/* Active toggle */}
      <TableCell>
        <Switch
          checked={edit.is_active}
          onCheckedChange={v => set("is_active", v)}
        />
      </TableCell>

      {/* Actions */}
      <TableCell>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            disabled={!dirty || saving}
            onClick={save}
          >
            {saving
              ? <RefreshCw className="w-3 h-3 animate-spin" />
              : <><Save className="w-3 h-3 mr-1" />Save</>}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-red-400 hover:text-red-600 hover:bg-red-50"
            onClick={() => onDelete(rule.id)}
          >
            <Trash2 className="w-3 h-3" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}

// ─── Programs tab ─────────────────────────────────────────────────────────────

function ProgramsTab({ programs }: { programs: LenderProgram[] }) {
  if (!programs.length) return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-2 border rounded-lg">
      <AlertCircle className="w-5 h-5" />
      <p className="text-sm">No programs configured for this lender.</p>
    </div>
  )

  return (
    <div className="border rounded-lg overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-gray-50">
            <TableHead>Program Name</TableHead>
            <TableHead>Min Amount</TableHead>
            <TableHead>Max Amount</TableHead>
            <TableHead>Credit Tier</TableHead>
            <TableHead>Description</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {programs.map(p => (
            <TableRow key={p.id}>
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LenderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router  = useRouter()

  const [lender, setLender]         = useState<Lender | null>(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)
  const [tab, setTab]               = useState<"rules" | "programs">("rules")
  const [showInactive, setShowInactive] = useState(false)
  const [deleteId, setDeleteId]     = useState<number | null>(null)
  const [deleting, setDeleting]     = useState(false)

  async function load() {
    try {
      setLoading(true)
      setError(null)
      setLender(await getLender(Number(id)))
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to load lender.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  // ── Save rule ───────────────────────────────────────────────────────────────

  async function handleSave(ruleId: number, data: RowEdit) {
    await updateRule(Number(id), ruleId, data)
    // Optimistically update local state
    setLender(l => l ? {
      ...l,
      rules: l.rules.map(r => r.id === ruleId ? { ...r, ...data } : r),
    } : l)
  }

  // ── Delete rule ─────────────────────────────────────────────────────────────

  async function handleDelete() {
    if (deleteId == null) return
    setDeleting(true)
    try {
      await deleteRule(Number(id), deleteId)
      setLender(l => l ? { ...l, rules: l.rules.filter(r => r.id !== deleteId) } : l)
      toast.success("Rule deleted.")
    } catch {
      toast.error("Failed to delete rule.")
    } finally {
      setDeleting(false)
      setDeleteId(null)
    }
  }

  // ── States ──────────────────────────────────────────────────────────────────

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-400">
      <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading lender…
    </div>
  )

  if (error || !lender) return (
    <div className="flex flex-col items-center justify-center h-64 gap-4 text-gray-500">
      <AlertCircle className="w-8 h-8 text-red-400" />
      <p>{error ?? "Lender not found."}</p>
      <Button variant="outline" onClick={() => router.push("/lenders")}>Back to lenders</Button>
    </div>
  )

  // ── Derived ─────────────────────────────────────────────────────────────────

  const visibleRules = showInactive
    ? lender.rules
    : lender.rules.filter(r => r.is_active)

  const inactiveCount = lender.rules.filter(r => !r.is_active).length

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => router.push("/lenders")}
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-gray-600 mb-2 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back to lenders
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{lender.name}</h1>
            {lender.is_active
              ? <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">Active</Badge>
              : <Badge className="bg-gray-100 text-gray-500 border-gray-200">Inactive</Badge>}
          </div>
          {(lender.contact_email || lender.contact_phone || lender.contact_name) && (
            <p className="text-sm text-gray-400 mt-1">
              {[lender.contact_name, lender.contact_email, lender.contact_phone]
                .filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
      </div>

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
              ({t === "rules" ? lender.rules.length : lender.programs.length})
            </span>
          </button>
        ))}
      </div>

      {/* Rules tab */}
      {tab === "rules" && (
        <div className="space-y-4">

          {/* Toolbar */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              {visibleRules.length} rule{visibleRules.length !== 1 ? "s" : ""} shown
              {!showInactive && inactiveCount > 0 && (
                <span className="text-gray-400"> · {inactiveCount} inactive hidden</span>
              )}
            </p>
            {inactiveCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="flex items-center gap-2 text-xs"
                onClick={() => setShowInactive(v => !v)}
              >
                {showInactive
                  ? <><EyeOff className="w-3.5 h-3.5" /> Hide inactive</>
                  : <><Eye className="w-3.5 h-3.5" /> Show inactive ({inactiveCount})</>}
              </Button>
            )}
          </div>

          {visibleRules.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-2 border rounded-lg">
              <AlertCircle className="w-5 h-5" />
              <p className="text-sm">No active rules. Toggle to show inactive rules.</p>
            </div>
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
                    <TableHead>Active</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleRules.map(rule => (
                    <RuleRow
                      key={rule.id}
                      rule={rule}
                      onSave={handleSave}
                      onDelete={id => setDeleteId(id)}
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      )}

      {/* Programs tab */}
      {tab === "programs" && <ProgramsTab programs={lender.programs} />}

      {/* Delete confirm dialog */}
      <Dialog open={deleteId != null} onOpenChange={open => { if (!open) setDeleteId(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete rule?</DialogTitle>
            <DialogDescription>
              This will permanently remove the rule from this lender's policy. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3 mt-2">
            <Button variant="outline" onClick={() => setDeleteId(null)}>Cancel</Button>
            <Button
              variant="destructive"
              disabled={deleting}
              onClick={handleDelete}
            >
              {deleting ? <RefreshCw className="w-4 h-4 animate-spin" /> : "Delete"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

    </div>
  )
}