"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { uploadPDF, listIngestions } from "@/lib/api"
import { Ingestion } from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table"
import { toast } from "sonner"
import {
  Upload, RefreshCw, AlertCircle,
  FileText, ChevronRight, Loader2,
} from "lucide-react"

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusBadge(status: Ingestion["status"]) {
  switch (status) {
    case "APPROVED":
      return <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">Approved</Badge>
    case "REJECTED":
      return <Badge className="bg-red-100 text-red-700 border-red-200">Rejected</Badge>
    case "PENDING_REVIEW":
      return <Badge className="bg-amber-100 text-amber-700 border-amber-200">Pending Review</Badge>
    default:
      return <Badge className="bg-gray-100 text-gray-500 border-gray-200">{status}</Badge>
  }
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function IngestPage() {
  const router                      = useRouter()
  const inputRef                    = useRef<HTMLInputElement>(null)
  const [ingestions, setIngestions] = useState<Ingestion[]>([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)
  const [uploading, setUploading]   = useState(false)
  const [dragOver, setDragOver]     = useState(false)

  async function load() {
    try {
      setLoading(true)
      setError(null)
      const data = await listIngestions()
      setIngestions(data.sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      ))
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to load ingestions.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // ── Upload ────────────────────────────────────────────────────────────────

  async function handleUpload(file: File) {
    if (!file.name.endsWith(".pdf")) {
      toast.error("Only PDF files are supported.")
      return
    }
    setUploading(true)
    try {
      const { ingestion_id } = await uploadPDF(file)
      toast.success("PDF uploaded — extraction started.")
      router.push(`/ingest/${ingestion_id}`)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? "Upload failed.")
      setUploading(false)
    }
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-8">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">PDF Ingestion</h1>
        <p className="text-sm text-gray-500 mt-1">
          Upload a lender guideline PDF to extract and review its credit policy rules.
        </p>
      </div>

      {/* Drop zone */}
      <Card
        className={`border-2 border-dashed transition-colors cursor-pointer ${
          dragOver ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"
        }`}
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
          {uploading ? (
            <>
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
              <p className="text-sm text-gray-500">Uploading and starting extraction…</p>
            </>
          ) : (
            <>
              <Upload className="w-8 h-8 text-gray-300" />
              <p className="text-sm font-medium text-gray-600">
                Drop a PDF here or <span className="text-blue-600">browse</span>
              </p>
              <p className="text-xs text-gray-400">Lender guideline PDFs only</p>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={onFileChange}
          />
        </CardContent>
      </Card>

      {/* Ingestion list */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">
            Previous Ingestions
          </h2>
          <Button variant="outline" size="sm" onClick={load} className="flex items-center gap-2">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-40 text-gray-400">
            <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading…
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-40 gap-3 text-gray-500">
            <AlertCircle className="w-6 h-6 text-red-400" />
            <p className="text-sm">{error}</p>
            <Button variant="outline" size="sm" onClick={load}>Retry</Button>
          </div>
        ) : ingestions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 border rounded-lg text-gray-400">
            <FileText className="w-7 h-7" />
            <p className="text-sm">No ingestions yet. Upload a PDF to get started.</p>
          </div>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50">
                  <TableHead>Filename</TableHead>
                  <TableHead>Lender Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Rules</TableHead>
                  <TableHead>Programs</TableHead>
                  <TableHead>Uploaded</TableHead>
                  <TableHead className="w-8" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {ingestions.map(ing => (
                  <TableRow
                    key={ing.id}
                    className="cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => router.push(`/ingest/${ing.id}`)}
                  >
                    <TableCell className="font-medium text-gray-900 flex items-center gap-2">
                      <FileText className="w-4 h-4 text-gray-300 shrink-0" />
                      {ing.filename}
                    </TableCell>
                    <TableCell className="text-gray-600">
                      {ing.extracted?.lender_name ?? (
                        <span className="text-gray-300 italic">
                          {ing.status === "PENDING_REVIEW" ? "Extracting…" : "—"}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>{statusBadge(ing.status)}</TableCell>
                    <TableCell className="text-gray-600">
                      {ing.extracted?.rules?.length ?? "—"}
                    </TableCell>
                    <TableCell className="text-gray-600">
                      {ing.extracted?.programs?.length ?? "—"}
                    </TableCell>
                    <TableCell className="text-gray-400 text-sm whitespace-nowrap">
                      {new Date(ing.created_at).toLocaleDateString("en-US", {
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
    </div>
  )
}