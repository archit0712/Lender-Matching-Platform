"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { listLenders } from "@/lib/api"
import { Lender } from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table"
import { AlertCircle, RefreshCw, ChevronRight } from "lucide-react"

export default function LendersPage() {
  const router = useRouter()
  const [lenders, setLenders] = useState<Lender[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  async function load() {
    try {
      setLoading(true)
      setError(null)
      setLenders(await listLenders())
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to load lenders.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-400">
      <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading lenders…
    </div>
  )

  if (error) return (
    <div className="flex flex-col items-center justify-center h-64 gap-4 text-gray-500">
      <AlertCircle className="w-8 h-8 text-red-400" />
      <p>{error}</p>
      <Button variant="outline" onClick={load}>Retry</Button>
    </div>
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Lender Policies</h1>
        <p className="text-sm text-gray-500 mt-1">
          {lenders.length} lender{lenders.length !== 1 ? "s" : ""} configured · Click a row to view and edit rules
        </p>
      </div>

      {lenders.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3 border rounded-lg text-gray-400">
          <AlertCircle className="w-8 h-8" />
          <p className="text-sm">No lenders found. Upload a PDF to add one.</p>
          <Button variant="outline" size="sm" onClick={() => router.push("/ingest")}>
            Upload PDF
          </Button>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-gray-50">
                <TableHead>Lender</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Active Rules</TableHead>
                <TableHead>Programs</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead className="w-8" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {lenders.map(l => {
                const activeRules = l.rules.filter(r => r.is_active).length
                return (
                  <TableRow
                    key={l.id}
                    className="cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => router.push(`/lenders/${l.id}`)}
                  >
                    <TableCell>
                      <div className="font-medium text-gray-900">{l.name}</div>
                      {l.notes && (
                        <div className="text-xs text-gray-400 mt-0.5 truncate max-w-xs">{l.notes}</div>
                      )}
                    </TableCell>
                    <TableCell>
                      {l.is_active
                        ? <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">Active</Badge>
                        : <Badge className="bg-gray-100 text-gray-500 border-gray-200">Inactive</Badge>}
                    </TableCell>
                    <TableCell className="text-gray-700">
                      {activeRules}
                      <span className="text-gray-400 text-xs ml-1">/ {l.rules.length} total</span>
                    </TableCell>
                    <TableCell className="text-gray-700">{l.programs.length}</TableCell>
                    <TableCell className="text-gray-500 text-sm">
                      {l.contact_email ?? l.contact_phone ?? "—"}
                    </TableCell>
                    <TableCell className="text-gray-300">
                      <ChevronRight className="w-4 h-4" />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}