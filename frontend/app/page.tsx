import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Home() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">LenderMatch</h1>
        <p className="text-gray-500 mt-2">
          AI-powered loan underwriting — match borrowers to the right lenders instantly.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>New Application</CardTitle>
            <CardDescription>Submit a loan application and get instant lender matches</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/apply">
              <Button className="w-full">Start Application</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Lender Policies</CardTitle>
            <CardDescription>View and edit lender credit policy rules</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/lenders">
              <Button variant="outline" className="w-full">View Lenders</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Upload PDF</CardTitle>
            <CardDescription>Add a new lender by uploading their guidelines PDF</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/ingest">
              <Button variant="outline" className="w-full">Upload Guidelines</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}