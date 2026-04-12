"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import {
  FileUp,
  RefreshCw,
  FileText,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Cog,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import {
  uploadInvoicePDF,
  listInvoiceIngestions,
  listInvoices,
  deleteInvoice,
} from "@/lib/api";
import type { InvoiceIngestionListItem, Invoice } from "@/lib/invoice_types";

/* ── helpers ─────────────────────────────────────────────── */

function statusBadge(status: string) {
  const map: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
    COMPLETED: {
      cls: "bg-emerald-50 text-emerald-700 border-emerald-200",
      icon: <CheckCircle2 className="w-3 h-3 mr-1" />,
      label: "Completed",
    },
    PROCESSING: {
      cls: "bg-blue-50 text-blue-700 border-blue-200",
      icon: <Cog className="w-3 h-3 mr-1 animate-spin" />,
      label: "Processing",
    },
    FAILED: {
      cls: "bg-red-50 text-red-700 border-red-200",
      icon: <XCircle className="w-3 h-3 mr-1" />,
      label: "Failed",
    },
  };
  const cfg = map[status] ?? {
    cls: "bg-amber-50 text-amber-700 border-amber-200",
    icon: <Clock className="w-3 h-3 mr-1" />,
    label: "Pending",
  };
  return (
    <Badge variant="outline" className={cfg.cls}>
      {cfg.icon}
      {cfg.label}
    </Badge>
  );
}

function fmt(n: number | null | undefined, currency = "USD") {
  if (n == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(n);
}

function relativeTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return new Date(iso).toLocaleDateString();
}

/* ── page ────────────────────────────────────────────────── */

export default function InvoicesPage() {
  const router = useRouter();

  const [ingestions, setIngestions] = useState<InvoiceIngestionListItem[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  /* fetch */
  const refresh = useCallback(async () => {
    try {
      const [ing, inv] = await Promise.all([
        listInvoiceIngestions(),
        listInvoices(),
      ]);
      setIngestions(ing);
      setInvoices(inv);
    } catch {
      toast.error("Failed to load invoice data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  /* auto-poll while any ingestion is still processing */
  const hasPending = ingestions.some(
    (i) => i.status === "PENDING" || i.status === "PROCESSING"
  );

  useEffect(() => {
    if (!hasPending) return;
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, [hasPending, refresh]);

  /* upload */
  async function handleUpload(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Please upload a PDF file.");
      return;
    }
    setUploading(true);
    try {
      const result = await uploadInvoicePDF(file);
      toast.success(`Uploaded "${file.name}" — extraction started.`);
      router.push(`/invoices/${result.id}?type=ingestion`);
    } catch {
      toast.error("Upload failed. Check that the backend is running.");
    } finally {
      setUploading(false);
    }
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = "";
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  }

  /* delete */
  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await deleteInvoice(id);
      toast.success("Invoice deleted.");
      refresh();
    } catch {
      toast.error("Delete failed.");
    } finally {
      setDeletingId(null);
    }
  }

  /* ── render ────────────────────────────────────────────── */
  return (
    <div className="space-y-8">
      {/* header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Invoices</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Upload invoice PDFs to extract structured data automatically.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => { setLoading(true); refresh(); }}
          disabled={loading}
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* upload zone */}
      <Card
        className={`border-2 border-dashed transition-all cursor-pointer ${
          dragOver
            ? "border-primary bg-primary/5 scale-[1.01]"
            : "border-muted-foreground/25 hover:border-primary/40"
        }`}
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
          {uploading ? (
            <Loader2 className="w-10 h-10 text-primary animate-spin" />
          ) : (
            <FileUp className="w-10 h-10 text-muted-foreground" />
          )}
          <div className="text-center">
            <p className="text-sm font-medium">
              {uploading ? "Uploading…" : "Drop an invoice PDF here or click to browse"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Supports scanned PDFs (OCR) and native-text PDFs
            </p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={onFileChange}
          />
        </CardContent>
      </Card>

      {/* recent uploads — only show if there are non-completed ingestions or it's useful */}
      {ingestions.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Recent Uploads</CardTitle>
            {hasPending && (
              <CardDescription className="flex items-center gap-1.5">
                <Loader2 className="w-3 h-3 animate-spin" />
                Extraction in progress — auto-refreshing…
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>File</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Uploaded</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ingestions.map((ing) => (
                  <TableRow key={ing.id}>
                    <TableCell className="font-medium">{ing.filename}</TableCell>
                    <TableCell>{statusBadge(ing.status)}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {relativeTime(ing.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link href={`/invoices/${ing.id}?type=ingestion`}>
                        <Button variant="ghost" size="sm">
                          View
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* extracted invoices */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Extracted Invoices</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && invoices.length === 0 ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : invoices.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-10 h-10 mx-auto text-muted-foreground/40 mb-3" />
              <p className="text-sm text-muted-foreground">
                No invoices yet. Upload a PDF to get started.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Buyer</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead className="text-right w-[100px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.map((inv) => (
                  <TableRow
                    key={inv.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/invoices/${inv.id}`)}
                  >
                    <TableCell className="font-medium">
                      {inv.invoice_number || "—"}
                    </TableCell>
                    <TableCell>{inv.vendor_name || "—"}</TableCell>
                    <TableCell>{inv.buyer_name || "—"}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {inv.invoice_date || "—"}
                    </TableCell>
                    <TableCell className="text-right font-semibold">
                      {fmt(inv.total_amount, inv.currency ?? "USD")}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Link href={`/invoices/${inv.id}`} onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" size="sm">
                            <FileText className="w-4 h-4" />
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm("Delete this invoice?")) handleDelete(inv.id);
                          }}
                          disabled={deletingId === inv.id}
                        >
                          {deletingId === inv.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4 text-muted-foreground hover:text-red-500" />
                          )}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
