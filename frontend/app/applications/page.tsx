"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { listApplications } from "@/lib/api"
import { Application } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table"
import { AlertCircle, RefreshCw, Plus, ChevronRight } from "lucide-react"

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusBadge(status: string) {
  switch (status.toUpperCase()) {
    case "MATCHED":
      return <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">Matched</Badge>
    case "SUBMITTED":
      return <Badge className="bg-blue-100 text-blue-700 border-blue-200">Submitted</Badge>
    case "ERROR":
      return <Badge className="bg-red-100 text-red-700 border-red-200">Error</Badge>
    default:
      return <Badge className="bg-gray-100 text-gray-500 border-gray-200 capitalize">{status.toLowerCase()}</Badge>
  }
}

function eligibilitySummary(app: Application) {
  const results = app.results ?? []
  if (!results.length) return <span className="text-gray-400">—</span>
  const eligible = results.filter(r => r.is_eligible).length
  return (
    <span className={eligible > 0 ? "text-emerald-600 font-medium" : "text-red-500"}>
      {eligible} / {results.length} lenders
    </span>
  )
}

function bestFit(app: Application) {
  const results = app.results ?? []
  const eligible = results.filter(r => r.is_eligible)
  if (!eligible.length) return <span className="text-gray-400">—</span>
  const top = Math.max(...eligible.map(r => r.fit_score))
  const color = top >= 75 ? "text-emerald-600" : top >= 50 ? "text-amber-600" : "text-red-500"
  return <span className={`font-semibold ${color}`}>{top}<span className="text-gray-400 font-normal">/100</span></span>
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ApplicationsPage() {
  const router = useRouter()
  const [apps, setApps]       = useState<Application[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  async function load() {
    try {
      setLoading(true)
      setError(null)
      const data = await listApplications()
      // Newest first
      setApps(data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()))
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to load applications.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // ── States ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading applications…
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 text-gray-500">
        <AlertCircle className="w-8 h-8 text-red-400" />
        <p>{error}</p>
        <Button variant="outline" onClick={load}>Retry</Button>
      </div>
    )
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Applications</h1>
          <p className="text-sm text-gray-500 mt-1">
            {apps.length} application{apps.length !== 1 ? "s" : ""} total
          </p>
        </div>
        <Button onClick={() => router.push("/apply")} className="flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Application
        </Button>
      </div>

      {/* Empty state */}
      {apps.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-4 border rounded-lg text-gray-400">
          <AlertCircle className="w-8 h-8" />
          <p className="text-sm">No applications yet.</p>
          <Button onClick={() => router.push("/apply")} variant="outline" size="sm">
            Create your first application
          </Button>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-gray-50">
                <TableHead className="w-12">#</TableHead>
                <TableHead>Business</TableHead>
                <TableHead>Industry</TableHead>
                <TableHead>Loan Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Eligible Lenders</TableHead>
                <TableHead>Best Fit</TableHead>
                <TableHead>Date</TableHead>
                <TableHead className="w-8" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {apps.map(app => (
                <TableRow
                  key={app.id}
                  className="cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => router.push(`/applications/${app.id}`)}
                >
                  <TableCell className="text-gray-400 text-sm">{app.id}</TableCell>
                  <TableCell className="font-medium text-gray-900">
                    {app.borrower.business_name}
                  </TableCell>
                  <TableCell className="text-gray-500 capitalize">
                    {app.borrower.industry}
                  </TableCell>
                  <TableCell className="text-gray-700">
                    {app.loan_request.amount
                      ? `$${app.loan_request.amount.toLocaleString()}`
                      : "—"}
                  </TableCell>
                  <TableCell>{statusBadge(app.status)}</TableCell>
                  <TableCell>{eligibilitySummary(app)}</TableCell>
                  <TableCell>{bestFit(app)}</TableCell>
                  <TableCell className="text-gray-400 text-sm whitespace-nowrap">
                    {new Date(app.created_at).toLocaleDateString("en-US", {
                      month: "short", day: "numeric", year: "numeric",
                    })}
                  </TableCell>
                  <TableCell className="text-gray-300">
                    <ChevronRight className="w-4 h-4" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}