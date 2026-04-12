"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowLeft,
  Download,
  Loader2,
  FileText,
  Building2,
  User,
  Calendar,
  DollarSign,
  Copy,
  CheckCircle2,
  XCircle,
  Code2,
  Trash2,
  ReceiptText,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import {
  getInvoice,
  getInvoiceIngestion,
  getInvoiceJSON,
  deleteInvoice,
} from "@/lib/api";
import type { Invoice, InvoiceIngestion } from "@/lib/invoice_types";

/* ── helpers ─────────────────────────────────────────────── */

function fmt(n: number | null | undefined, currency = "USD") {
  if (n == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(n);
}

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex justify-between py-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-right max-w-[65%] break-words">{value}</span>
    </div>
  );
}

/* ── page ────────────────────────────────────────────────── */

export default function InvoiceDetailPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const id = params.id as string;
  const isIngestion = searchParams.get("type") === "ingestion";

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [ingestion, setIngestion] = useState<InvoiceIngestion | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showJson, setShowJson] = useState(false);
  const [jsonData, setJsonData] = useState<string | null>(null);
  const [jsonLoading, setJsonLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);

  /* ── fetch ─────────────────────────────────────────────── */
  const load = useCallback(async () => {
    try {
      setError(null);
      if (isIngestion) {
        const data = await getInvoiceIngestion(id);
        setIngestion(data);
        if (data.invoice) setInvoice(data.invoice);
      } else {
        const data = await getInvoice(id);
        setInvoice(data);
      }
    } catch {
      setError("Failed to load invoice data.");
    } finally {
      setLoading(false);
    }
  }, [id, isIngestion]);

  useEffect(() => { load(); }, [load]);

  /* poll while ingestion is processing */
  useEffect(() => {
    if (!isIngestion || !ingestion) return;
    if (ingestion.status === "COMPLETED" || ingestion.status === "FAILED") return;

    const interval = setInterval(async () => {
      try {
        const data = await getInvoiceIngestion(id);
        setIngestion(data);
        if (data.invoice) setInvoice(data.invoice);
        if (data.status === "COMPLETED") {
          toast.success("Invoice extraction completed!");
          clearInterval(interval);
        } else if (data.status === "FAILED") {
          toast.error("Invoice extraction failed.");
          clearInterval(interval);
        }
      } catch { /* ignore */ }
    }, 3000);

    return () => clearInterval(interval);
  }, [id, isIngestion, ingestion?.status, ingestion]);

  /* ── JSON toggle ───────────────────────────────────────── */
  async function toggleJson() {
    if (showJson) {
      setShowJson(false);
      return;
    }
    if (jsonData) {
      setShowJson(true);
      return;
    }
    if (!invoice) return;
    setJsonLoading(true);
    try {
      const data = await getInvoiceJSON(invoice.id);
      setJsonData(JSON.stringify(data, null, 2));
      setShowJson(true);
    } catch {
      toast.error("Failed to load JSON.");
    } finally {
      setJsonLoading(false);
    }
  }

  function handleCopy() {
    if (!jsonData) return;
    navigator.clipboard.writeText(jsonData);
    setCopied(true);
    toast.success("Copied to clipboard.");
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownloadJson() {
    if (!jsonData || !invoice) return;
    const blob = new Blob([jsonData], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `invoice-${invoice.invoice_number || invoice.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  /* ── delete ────────────────────────────────────────────── */
  async function handleDelete() {
    if (!invoice) return;
    if (!confirm("Delete this invoice? This action cannot be undone.")) return;
    setDeleting(true);
    try {
      await deleteInvoice(invoice.id);
      toast.success("Invoice deleted.");
      router.push("/invoices");
    } catch {
      toast.error("Delete failed.");
      setDeleting(false);
    }
  }

  const currency = invoice?.currency ?? "USD";

  /* ── loading ───────────────────────────────────────────── */
  if (loading) {
    return (
      <div className="flex justify-center items-center py-24">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  /* ── error ─────────────────────────────────────────────── */
  if (error) {
    return (
      <div className="space-y-6">
        <BackButton />
        <Card>
          <CardContent className="flex flex-col items-center py-16 gap-3">
            <XCircle className="w-10 h-10 text-red-400" />
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button variant="outline" size="sm" onClick={() => { setLoading(true); load(); }}>
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  /* ── ingestion still processing ────────────────────────── */
  if (isIngestion && ingestion && !invoice) {
    const isFailed = ingestion.status === "FAILED";
    return (
      <div className="space-y-6">
        <BackButton />
        <Card>
          <CardContent className="flex flex-col items-center py-20 gap-4">
            {isFailed ? (
              <>
                <XCircle className="w-14 h-14 text-red-400" />
                <h2 className="text-lg font-semibold">Extraction Failed</h2>
                <p className="text-sm text-muted-foreground max-w-md text-center">
                  {ingestion.error_message || "An unknown error occurred during extraction."}
                </p>
                <Button variant="outline" size="sm" onClick={() => router.push("/invoices")}>
                  Back to Invoices
                </Button>
              </>
            ) : (
              <>
                <div className="relative">
                  <ReceiptText className="w-14 h-14 text-muted-foreground/30" />
                  <Loader2 className="w-6 h-6 animate-spin text-primary absolute -bottom-1 -right-1" />
                </div>
                <h2 className="text-lg font-semibold">Extracting Invoice Data…</h2>
                <p className="text-sm text-muted-foreground text-center max-w-sm">
                  Processing <span className="font-medium">{ingestion.filename}</span>.
                  This typically takes 15–45 seconds for scanned PDFs.
                </p>
                <div className="flex gap-1 mt-2">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="w-2 h-2 rounded-full bg-primary animate-pulse"
                      style={{ animationDelay: `${i * 300}ms` }}
                    />
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  /* ── not found ─────────────────────────────────────────── */
  if (!invoice) {
    return (
      <div className="space-y-6">
        <BackButton />
        <Card>
          <CardContent className="flex flex-col items-center py-16 gap-3">
            <FileText className="w-10 h-10 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">Invoice not found.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  /* ── main detail ───────────────────────────────────────── */
  return (
    <div className="space-y-6">
      {/* top bar */}
      <div className="flex items-center justify-between">
        <BackButton />
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={toggleJson}
            disabled={jsonLoading}
          >
            {jsonLoading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Code2 className="w-4 h-4 mr-2" />
            )}
            {showJson ? "Hide JSON" : "View JSON"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDelete}
            disabled={deleting}
          >
            {deleting ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Trash2 className="w-4 h-4 mr-2" />
            )}
            Delete
          </Button>
        </div>
      </div>

      {/* header with total */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight">
            Invoice {invoice.invoice_number || "—"}
          </h1>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-sm text-muted-foreground">
            {ingestion && (
              <span>
                Extracted from <span className="font-medium">{ingestion.filename}</span>
              </span>
            )}
            {invoice.invoice_date && <span>Dated {invoice.invoice_date}</span>}
            {invoice.due_date && (
              <span>
                Due{" "}
                <span className="font-medium text-foreground">{invoice.due_date}</span>
              </span>
            )}
          </div>
        </div>
        {invoice.total_amount != null && (
          <div className="text-right shrink-0">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">
              Amount Due
            </p>
            <p className="text-3xl font-bold tabular-nums tracking-tight">
              {fmt(invoice.amount_due ?? invoice.total_amount, currency)}
            </p>
          </div>
        )}
      </div>

      {/* JSON viewer */}
      {showJson && jsonData && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">Extracted JSON</CardTitle>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={handleCopy}>
                {copied ? (
                  <CheckCircle2 className="w-4 h-4 mr-1 text-emerald-600" />
                ) : (
                  <Copy className="w-4 h-4 mr-1" />
                )}
                {copied ? "Copied" : "Copy"}
              </Button>
              <Button variant="ghost" size="sm" onClick={handleDownloadJson}>
                <Download className="w-4 h-4 mr-1" /> Download
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <pre className="bg-muted rounded-lg p-4 text-xs overflow-auto max-h-[28rem] font-mono leading-relaxed">
              {jsonData}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* info cards */}
      <div className="grid md:grid-cols-3 gap-4">
        {/* vendor */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground flex items-center gap-2">
              <Building2 className="w-3.5 h-3.5" /> Vendor
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-0 pt-0">
            {invoice.vendor_name && (
              <p className="font-semibold text-sm mb-1">{invoice.vendor_name}</p>
            )}
            <InfoRow label="Address" value={invoice.vendor_address} />
            <InfoRow label="Tax ID" value={invoice.vendor_tax_id} />
            <InfoRow label="Email" value={invoice.vendor_email} />
            <InfoRow label="Phone" value={invoice.vendor_phone} />
            {!invoice.vendor_name && !invoice.vendor_address && (
              <p className="text-xs text-muted-foreground py-2">No vendor data extracted</p>
            )}
          </CardContent>
        </Card>

        {/* buyer */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground flex items-center gap-2">
              <User className="w-3.5 h-3.5" /> Buyer / Account Holder
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-0 pt-0">
            {invoice.buyer_name && (
              <p className="font-semibold text-sm mb-1">{invoice.buyer_name}</p>
            )}
            <InfoRow label="Address" value={invoice.buyer_address} />
            <InfoRow label="Tax ID" value={invoice.buyer_tax_id} />
            {(invoice.ship_to_name || invoice.ship_to_address) && (
              <>
                <Separator className="my-2" />
                <InfoRow label="Ship To" value={invoice.ship_to_name} />
                <InfoRow label="Address" value={invoice.ship_to_address} />
              </>
            )}
            {!invoice.buyer_name && !invoice.buyer_address && (
              <p className="text-xs text-muted-foreground py-2">No buyer data extracted</p>
            )}
          </CardContent>
        </Card>

        {/* dates & payment */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground flex items-center gap-2">
              <Calendar className="w-3.5 h-3.5" /> Dates & Payment
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-0 pt-0">
            <InfoRow label="Invoice Date" value={invoice.invoice_date} />
            <InfoRow label="Due Date" value={invoice.due_date} />
            <InfoRow label="PO Number" value={invoice.po_number} />
            <InfoRow label="Terms" value={invoice.payment_terms} />
            <InfoRow label="Method" value={invoice.payment_method} />
            {invoice.bank_details && (
              <InfoRow label="Bank Details" value={invoice.bank_details} />
            )}
          </CardContent>
        </Card>
      </div>

      {/* line items */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">
              Line Items
              {invoice.line_items.length > 0 && (
                <Badge variant="secondary" className="ml-2 text-xs font-normal">
                  {invoice.line_items.length}
                </Badge>
              )}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {invoice.line_items.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">No line items extracted.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table className="table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10 whitespace-normal break-words">#</TableHead>
                    <TableHead className="w-[55%] whitespace-normal break-words">
                      Description
                    </TableHead>
                    <TableHead className="whitespace-normal break-words text-right">
                      Qty
                    </TableHead>
                    <TableHead className="whitespace-normal break-words text-right">
                      Unit Price
                    </TableHead>
                    <TableHead className="whitespace-normal break-words text-right">
                      Amount
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoice.line_items.map((li, idx) => (
                    <TableRow key={li.id}>
                      <TableCell className="whitespace-normal break-words text-muted-foreground tabular-nums align-top">
                        {li.line_number ?? idx + 1}
                      </TableCell>
                      <TableCell className="whitespace-normal break-words align-top">
                        <span className="font-medium break-words whitespace-normal">
                          {li.description || "—"}
                        </span>
                        {li.sku && (
                          <span className="ml-2 text-xs text-muted-foreground break-words whitespace-normal">
                            ({li.sku})
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="whitespace-normal break-words text-right tabular-nums align-top">
                        {li.quantity != null
                          ? `${li.quantity}${li.unit ? ` ${li.unit}` : ""}`
                          : "—"}
                      </TableCell>
                      <TableCell className="whitespace-normal break-words text-right tabular-nums align-top">
                        {fmt(li.unit_price, currency)}
                      </TableCell>
                      <TableCell className="whitespace-normal break-words text-right font-medium tabular-nums align-top">
                        {fmt(li.amount, currency)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* totals */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <DollarSign className="w-5 h-5" /> Totals
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-w-xs ml-auto space-y-0">
            <TotalRow label="Subtotal" value={fmt(invoice.subtotal, currency)} />
            {invoice.discount_amount != null && (
              <TotalRow
                label="Discount"
                value={`−${fmt(invoice.discount_amount, currency)}`}
                muted
              />
            )}
            {invoice.shipping_amount != null && (
              <TotalRow label="Shipping" value={fmt(invoice.shipping_amount, currency)} muted />
            )}
            <TotalRow
              label={`Tax${invoice.tax_rate != null ? ` (${invoice.tax_rate}%)` : ""}`}
              value={fmt(invoice.tax_amount, currency)}
            />
            <Separator className="my-2" />
            <div className="flex justify-between py-2">
              <span className="font-semibold">Total</span>
              <span className="font-bold text-xl tabular-nums">
                {fmt(invoice.total_amount, currency)}
              </span>
            </div>
            {invoice.amount_due != null &&
              invoice.amount_due !== invoice.total_amount && (
                <TotalRow
                  label="Amount Due"
                  value={fmt(invoice.amount_due, currency)}
                  bold
                />
              )}
          </div>
        </CardContent>
      </Card>

      {/* notes */}
      {invoice.notes && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-wrap leading-relaxed">
              {invoice.notes}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ── small components ────────────────────────────────────── */

function BackButton() {
  return (
    <Link href="/invoices">
      <Button variant="ghost" size="sm">
        <ArrowLeft className="w-4 h-4 mr-2" /> Back to Invoices
      </Button>
    </Link>
  );
}

function TotalRow({
  label,
  value,
  muted,
  bold,
}: {
  label: string;
  value: string;
  muted?: boolean;
  bold?: boolean;
}) {
  return (
    <div className="flex justify-between py-1.5 text-sm">
      <span className={muted ? "text-muted-foreground" : ""}>{label}</span>
      <span className={`tabular-nums ${bold ? "font-semibold" : "font-medium"}`}>
        {value}
      </span>
    </div>
  );
}
