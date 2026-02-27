"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

const LINKS = [
  { href: "/",              label: "Home"            },
  { href: "/apply",         label: "New Application" },
  { href: "/applications",  label: "Applications"    },
  { href: "/lenders",       label: "Lender Policies" },
  { href: "/ingest",        label: "Upload PDF"      },
]

export function Nav() {
  const path = usePathname()

  // Active: exact match for "/", prefix match for everything else
  function isActive(href: string) {
    return href === "/" ? path === "/" : path.startsWith(href)
  }

  return (
    <nav className="border-b bg-white sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-6 flex items-center gap-6 h-14">
        <Link href="/" className="font-bold text-gray-900 text-base mr-2">
          LenderMatch
        </Link>
        {LINKS.slice(1).map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={`text-sm transition-colors ${
              isActive(href)
                ? "text-blue-600 font-medium"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            {label}
          </Link>
        ))}
      </div>
    </nav>
  )
}