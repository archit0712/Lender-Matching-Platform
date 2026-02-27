"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getApplication, rerunUnderwriting } from "@/lib/api";
import { Application, MatchResult, CriteriaDetail } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  ArrowLeft,
  Building2,
  User,
  Truck,
  DollarSign,
} from "lucide-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fitColor(score: number) {
  if (score >= 75) return "text-emerald-600";
  if (score >= 50) return "text-amber-600";
  return "text-red-500";
}

function fitBg(score: number) {
  if (score >= 75) return "bg-emerald-50 border-emerald-200";
  if (score >= 50) return "bg-amber-50 border-amber-200";
  return "bg-red-50 border-red-200";
}

// ─── Criteria row ─────────────────────────────────────────────────────────────

function CriteriaRow({ c }: { c: CriteriaDetail }) {
  return (
    <TableRow className="text-sm">
      <TableCell className="w-8">
        {c.passed ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
        ) : (
          <XCircle className="w-4 h-4 text-red-500" />
        )}
      </TableCell>
      <TableCell className="font-mono text-xs text-gray-500 whitespace-nowrap">
        {c.explanation?.split(":")[0] ?? `Rule #${c.rule_id}`}
      </TableCell>
      <TableCell className="text-gray-700">{c.actual_value ?? "—"}</TableCell>
      <TableCell className="text-gray-700">{c.required_value ?? "—"}</TableCell>
      <TableCell className="text-gray-500 italic">{c.explanation ?? "—"}</TableCell>
    </TableRow>
  );
}

// ─── Lender result row (expandable) ──────────────────────────────────────────

function LenderRow({ r, rank }: { r: MatchResult; rank: number }) {
  const [open, setOpen] = useState(false);
  const failed = r.criteria.filter((c) => !c.passed);
  const passed = r.criteria.filter((c) => c.passed);

  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        <TableCell className="text-gray-400 text-sm font-medium w-8">{rank}</TableCell>
        <TableCell className="font-medium text-gray-900">{r.lender.name}</TableCell>
        <TableCell>
          {r.is_eligible ? (
            <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">Eligible</Badge>
          ) : (
            <Badge className="bg-red-100 text-red-700 border-red-200">Ineligible</Badge>
          )}
        </TableCell>
        <TableCell>
          {r.is_eligible ? (
            <span className={`font-semibold ${fitColor(r.fit_score)}`}>
              {r.fit_score}
              <span className="text-gray-400 font-normal">/100</span>
            </span>
          ) : (
            <span className="text-gray-400">—</span>
          )}
        </TableCell>
        <TableCell className="text-sm">
          {failed.length > 0 ? (
            <span className="text-red-500">{failed.length} failed</span>
          ) : (
            <span className="text-emerald-600">All passed</span>
          )}
        </TableCell>
        <TableCell className="text-gray-400">
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </TableCell>
      </TableRow>

      {/* Expanded criteria */}
      {open && (
        <TableRow>
          <TableCell colSpan={6} className="p-0 bg-transparent">
            <div className={`mx-4 mb-4 rounded-lg border ${fitBg(r.fit_score)} overflow-hidden`}>
              {r.criteria.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs uppercase tracking-wide border-b border-gray-200 hover:bg-transparent">
                      <TableHead className="w-8" />
                      <TableHead>Rule</TableHead>
                      <TableHead>Actual</TableHead>
                      <TableHead>Required</TableHead>
                      <TableHead>Explanation</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {failed.map((c, i) => <CriteriaRow key={`f${i}`} c={c} />)}
                    {failed.length > 0 && passed.length > 0 && (
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={5} className="p-0">
                          <div className="border-t border-dashed border-gray-300" />
                        </TableCell>
                      </TableRow>
                    )}
                    {passed.map((c, i) => <CriteriaRow key={`p${i}`} c={c} />)}
                  </TableBody>
                </Table>
              ) : (
                <p className="px-4 py-3 text-sm text-gray-500 italic">
                  No criteria details available.
                </p>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

// ─── Info card ────────────────────────────────────────────────────────────────

function InfoCard({
  icon, title, rows,
}: {
  icon: React.ReactNode;
  title: string;
  rows: { label: string; value: string | number | null | undefined }[];
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-2">
          {icon}{title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {rows.map((r) => (
          <div key={r.label} className="flex justify-between text-sm">
            <span className="text-gray-500">{r.label}</span>
            <span className="font-medium text-gray-900">{r.value ?? "—"}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [app, setApp] = useState<Application | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const data = await getApplication(Number(id));
      setApp(data);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to load application.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);

  async function handleRerun() {
    try {
      setRerunning(true);
      const updated = await rerunUnderwriting(Number(id));
      setApp(updated);
      toast.success("Matching re-run complete.");
    } catch {
      toast.error("Failed to re-run matching.");
    } finally {
      setRerunning(false);
    }
  }

  // ── States ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        <RefreshCw className="w-5 h-5 animate-spin mr-2" />
        Loading application…
      </div>
    );
  }

  if (error || !app) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 text-gray-500">
        <AlertCircle className="w-8 h-8 text-red-400" />
        <p>{error ?? "Application not found."}</p>
        <Button variant="outline" onClick={() => router.push("/")}>Go home</Button>
      </div>
    );
  }

  // ── Derived ───────────────────────────────────────────────────────────────

  const { borrower: b, loan_request: lr } = app;
  const g = b.guarantors?.[0];
  const bc = b.biz_credit;

  const sorted = [...app.results].sort((a, z) => {
    if (a.is_eligible !== z.is_eligible) return a.is_eligible ? -1 : 1;
    return z.fit_score - a.fit_score;
  });

  const eligibleCount = sorted.filter((r) => r.is_eligible).length;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-8">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => router.push("/")}
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-gray-600 mb-2 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <h1 className="text-2xl font-bold text-gray-900">{b.business_name}</h1>
          <p className="text-gray-500 text-sm mt-1">
            Application #{app.id} · <span className="capitalize">{app.status.toLowerCase()}</span> ·{" "}
            {new Date(app.created_at).toLocaleDateString("en-US", {
              month: "short", day: "numeric", year: "numeric",
            })}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRerun}
          disabled={rerunning}
          className="flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${rerunning ? "animate-spin" : ""}`} />
          Re-run matching
        </Button>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <InfoCard
          icon={<Building2 className="w-4 h-4" />}
          title="Business"
          rows={[
            { label: "Industry",          value: b.industry },
            { label: "State",             value: b.state },
            { label: "Years in business", value: b.years_in_business },
            { label: "Annual revenue",    value: b.annual_revenue != null ? `$${b.annual_revenue.toLocaleString()}` : null },
          ]}
        />
        <InfoCard
          icon={<User className="w-4 h-4" />}
          title="Guarantor"
          rows={[
            { label: "Name",      value: g?.full_name },
            { label: "FICO",      value: g?.fico_score },
            { label: "Ownership", value: g?.ownership_pct != null ? `${g.ownership_pct}%` : null },
            { label: "Homeowner", value: g ? (g.is_homeowner ? "Yes" : "No") : null },
          ]}
        />
        <InfoCard
          icon={<DollarSign className="w-4 h-4" />}
          title="Business Credit"
          rows={[
            { label: "PayNet",            value: bc?.paynet_score },
            { label: "Comparable credit", value: bc?.comparable_credit_amount != null ? `$${bc.comparable_credit_amount.toLocaleString()}` : null },
          ]}
        />
        <InfoCard
          icon={<Truck className="w-4 h-4" />}
          title="Loan Request"
          rows={[
            { label: "Amount",    value: `$${lr.amount.toLocaleString()}` },
            { label: "Equipment", value: lr.equipment_type },
            { label: "Year",      value: lr.equipment_year },
            { label: "Mileage",   value: lr.mileage != null ? lr.mileage.toLocaleString() : null },
          ]}
        />
      </div>

      <Separator />

      {/* Match results */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Lender Match Results</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {eligibleCount} of {sorted.length} lenders eligible · Click any row to expand criteria
            </p>
          </div>
          {eligibleCount > 0 && (
            <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-sm px-3 py-1">
              {eligibleCount} match{eligibleCount !== 1 ? "es" : ""}
            </Badge>
          )}
        </div>

        {sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-2 border rounded-lg">
            <AlertCircle className="w-6 h-6" />
            <p>No match results yet. Try re-running matching.</p>
          </div>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50">
                  <TableHead className="w-8">#</TableHead>
                  <TableHead>Lender</TableHead>
                  <TableHead>Eligible</TableHead>
                  <TableHead>Fit Score</TableHead>
                  <TableHead>Criteria</TableHead>
                  <TableHead className="w-8" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((r, i) => (
                  <LenderRow key={r.id} r={r} rank={i + 1} />
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}