"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { submitApplication } from "@/lib/api"
import type { ApplicationFormData } from "@/lib/types"

// ── Constants ─────────────────────────────────────────────────

const INDUSTRIES = [
  { value: "trucking",      label: "Trucking" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "commercial",    label: "Commercial" },
  { value: "construction",  label: "Construction" },
  { value: "logging",       label: "Logging" },
  { value: "medical",       label: "Medical" },
  { value: "restaurant",    label: "Restaurant" },
  { value: "other",         label: "Other" },
]

const EQUIPMENT_TYPES = [
  { value: "class_8_truck",   label: "Class 8 Truck" },
  { value: "dump_truck",      label: "Dump Truck" },
  { value: "medium_duty",     label: "Medium Duty Truck" },
  { value: "light_duty",      label: "Light Duty Truck" },
  { value: "trailer",         label: "Trailer" },
  { value: "reefer_trailer",  label: "Reefer Trailer" },
  { value: "machine_tool",    label: "Machine Tool" },
  { value: "construction",    label: "Construction Equipment" },
  { value: "forklift",        label: "Forklift / Material Handling" },
  { value: "medical",         label: "Medical Equipment" },
  { value: "restaurant",      label: "Restaurant Equipment" },
  { value: "other",           label: "Other" },
]

const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
  "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
  "VA","WA","WV","WI","WY",
]

const STEPS = ["Business Info", "Guarantor", "Business Credit", "Loan Request"]

// ── Default form state ────────────────────────────────────────

const DEFAULTS: ApplicationFormData = {
  business_name: "", industry: "", state: "",
  years_in_business: 0, annual_revenue: 0, num_trucks: 0,
  full_name: "", fico_score: 0, ownership_pct: 100,
  has_bankruptcy: false, bankruptcy_discharged_yrs: 0,
  is_homeowner: false, has_cdl: false,
  paynet_score: 0, comparable_credit_amount: 0,
  loan_amount: 0, equipment_type: "", equipment_year: new Date().getFullYear(),
  mileage: 0, is_private_party: false,
}

// ── Helper components ─────────────────────────────────────────

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label className="text-sm font-medium">{label}</Label>
      {children}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}

function NumericInput({ value, onChange, placeholder, min = 0 }: {
  value: number; onChange: (v: number) => void; placeholder?: string; min?: number
}) {
  return (
    <Input
      type="number"
      min={min}
      value={value || ""}
      placeholder={placeholder}
      onChange={e => onChange(parseFloat(e.target.value) || 0)}
    />
  )
}

// ── Main component ────────────────────────────────────────────

export default function ApplyPage() {
  const router  = useRouter()
  const [step, setStep]     = useState(0)
  const [form, setForm]     = useState<ApplicationFormData>(DEFAULTS)
  const [errors, setErrors] = useState<Partial<Record<keyof ApplicationFormData, string>>>({})
  const [loading, setLoading] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const set = <K extends keyof ApplicationFormData>(k: K, v: ApplicationFormData[K]) =>
    setForm(f => ({ ...f, [k]: v }))

  // ── Validation per step ───────────────────────────────────
  function validate(): boolean {
    const e: typeof errors = {}
    if (step === 0) {
      if (!form.business_name.trim()) e.business_name = "Required"
      if (!form.industry)            e.industry       = "Required"
      if (!form.state)               e.state          = "Required"
      if (form.years_in_business <= 0) e.years_in_business = "Must be greater than 0"
    }
    if (step === 1) {
      if (!form.full_name.trim())  e.full_name   = "Required"
      if (form.fico_score < 300 || form.fico_score > 850) e.fico_score = "Must be between 300–850"
      if (form.ownership_pct <= 0) e.ownership_pct = "Required"
      if (form.has_bankruptcy && form.bankruptcy_discharged_yrs <= 0)
        e.bankruptcy_discharged_yrs = "Required when bankruptcy is selected"
    }
    if (step === 3) {
      if (form.loan_amount <= 0)    e.loan_amount    = "Must be greater than 0"
      if (!form.equipment_type)     e.equipment_type = "Required"
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function next() { if (validate()) setStep(s => s + 1) }
  function back() { setStep(s => s - 1) }

  async function submit() {
    if (!validate()) return
    setLoading(true)
    setSubmitError(null)
    try {
      const app = await submitApplication(form)
      router.push(`/applications/${app.id}`)
    } catch (err: any) {
      setSubmitError(err.response?.data?.detail ?? "Submission failed. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  // ── Steps ─────────────────────────────────────────────────

  const stepContent = [

    // Step 0: Business Info
    <div key="business" className="space-y-4">
      <Field label="Business Name" error={errors.business_name}>
        <Input
          value={form.business_name}
          placeholder="Acme Trucking LLC"
          onChange={e => set("business_name", e.target.value)}
        />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Industry" error={errors.industry}>
          <Select value={form.industry} onValueChange={v => set("industry", v)}>
            <SelectTrigger><SelectValue placeholder="Select industry" /></SelectTrigger>
            <SelectContent>
              {INDUSTRIES.map(i => <SelectItem key={i.value} value={i.value}>{i.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>

        <Field label="State" error={errors.state}>
          <Select value={form.state} onValueChange={v => set("state", v)}>
            <SelectTrigger><SelectValue placeholder="Select state" /></SelectTrigger>
            <SelectContent>
              {US_STATES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Years in Business" error={errors.years_in_business}>
          <NumericInput value={form.years_in_business} onChange={v => set("years_in_business", v)} placeholder="5" />
        </Field>

        <Field label="Annual Revenue ($)">
          <NumericInput value={form.annual_revenue} onChange={v => set("annual_revenue", v)} placeholder="500000" />
        </Field>
      </div>

      {form.industry === "trucking" && (
        <Field label="Number of Trucks in Fleet">
          <NumericInput value={form.num_trucks} onChange={v => set("num_trucks", v)} placeholder="5" />
        </Field>
      )}
    </div>,

    // Step 1: Personal Guarantor
    <div key="guarantor" className="space-y-4">
      <Field label="Full Name" error={errors.full_name}>
        <Input value={form.full_name} placeholder="John Smith"
          onChange={e => set("full_name", e.target.value)} />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="FICO Score" error={errors.fico_score}>
          <NumericInput value={form.fico_score} onChange={v => set("fico_score", v)} placeholder="700" min={300} />
        </Field>

        <Field label="Ownership %" error={errors.ownership_pct}>
          <NumericInput value={form.ownership_pct} onChange={v => set("ownership_pct", v)} placeholder="100" />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Homeowner">
          <div className="flex items-center gap-3 pt-2">
            <Switch checked={form.is_homeowner} onCheckedChange={v => set("is_homeowner", v)} />
            <span className="text-sm text-gray-600">{form.is_homeowner ? "Yes" : "No"}</span>
          </div>
        </Field>

        <Field label="Has CDL">
          <div className="flex items-center gap-3 pt-2">
            <Switch checked={form.has_cdl} onCheckedChange={v => set("has_cdl", v)} />
            <span className="text-sm text-gray-600">{form.has_cdl ? "Yes" : "No"}</span>
          </div>
        </Field>
      </div>

      <Field label="Previous Bankruptcy">
        <div className="flex items-center gap-3 pt-2">
          <Switch checked={form.has_bankruptcy} onCheckedChange={v => set("has_bankruptcy", v)} />
          <span className="text-sm text-gray-600">{form.has_bankruptcy ? "Yes" : "No"}</span>
        </div>
      </Field>

      {form.has_bankruptcy && (
        <Field label="Years Since Discharge" error={errors.bankruptcy_discharged_yrs}>
          <NumericInput
            value={form.bankruptcy_discharged_yrs}
            onChange={v => set("bankruptcy_discharged_yrs", v)}
            placeholder="7"
          />
        </Field>
      )}
    </div>,

    // Step 2: Business Credit
    <div key="credit" className="space-y-4">
      <p className="text-sm text-gray-500">
        Business credit information is optional but improves matching accuracy.
      </p>

      <Field label="PayNet Score">
        <NumericInput value={form.paynet_score} onChange={v => set("paynet_score", v)} placeholder="680" />
      </Field>

      <Field label="Comparable Commercial Credit Amount ($)">
        <NumericInput
          value={form.comparable_credit_amount}
          onChange={v => set("comparable_credit_amount", v)}
          placeholder="200000"
        />
        <p className="text-xs text-gray-400 mt-1">
          Existing commercial installment credit — used by some lenders to verify repayment capacity.
        </p>
      </Field>
    </div>,

    // Step 3: Loan Request
    <div key="loan" className="space-y-4">
      <Field label="Loan Amount ($)" error={errors.loan_amount}>
        <NumericInput value={form.loan_amount} onChange={v => set("loan_amount", v)} placeholder="150000" />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Equipment Type" error={errors.equipment_type}>
          <Select value={form.equipment_type} onValueChange={v => set("equipment_type", v)}>
            <SelectTrigger><SelectValue placeholder="Select type" /></SelectTrigger>
            <SelectContent>
              {EQUIPMENT_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>

        <Field label="Equipment Year">
          <NumericInput value={form.equipment_year} onChange={v => set("equipment_year", v)} placeholder="2020" />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Mileage">
          <NumericInput value={form.mileage} onChange={v => set("mileage", v)} placeholder="150000" />
        </Field>

        <Field label="Private Party Sale">
          <div className="flex items-center gap-3 pt-2">
            <Switch checked={form.is_private_party} onCheckedChange={v => set("is_private_party", v)} />
            <span className="text-sm text-gray-600">{form.is_private_party ? "Yes" : "No"}</span>
          </div>
        </Field>
      </div>
    </div>,
  ]

  // ── Render ────────────────────────────────────────────────

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">New Loan Application</h1>
        <p className="text-gray-500 text-sm mt-1">
          We'll match your application against all available lenders instantly.
        </p>
      </div>

      {/* Progress bar */}
      <div className="flex items-center gap-2">
        {STEPS.map((label, i) => (
          <div key={i} className="flex items-center gap-2 flex-1">
            <div className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold
              ${i < step ? "bg-blue-600 text-white" :
                i === step ? "bg-blue-100 text-blue-700 border-2 border-blue-600" :
                "bg-gray-100 text-gray-400"}`}>
              {i < step ? "✓" : i + 1}
            </div>
            <span className={`text-xs hidden sm:block ${i === step ? "text-blue-700 font-medium" : "text-gray-400"}`}>
              {label}
            </span>
            {i < STEPS.length - 1 && <div className={`flex-1 h-0.5 ${i < step ? "bg-blue-600" : "bg-gray-200"}`} />}
          </div>
        ))}
      </div>

      {/* Form card */}
      <Card>
        <CardHeader>
          <CardTitle>{STEPS[step]}</CardTitle>
          <CardDescription>
            {["Tell us about the business", "Primary owner / guarantor details",
              "Business credit profile", "What equipment are you financing?"][step]}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {stepContent[step]}

          {submitError && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {submitError}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Navigation buttons */}
      <div className="flex justify-between">
        <Button variant="outline" onClick={back} disabled={step === 0}>
          Back
        </Button>
        {step < STEPS.length - 1 ? (
          <Button onClick={next}>Next →</Button>
        ) : (
          <Button onClick={submit} disabled={loading}>
            {loading ? "Submitting..." : "Submit Application"}
          </Button>
        )}
      </div>
    </div>
  )
}