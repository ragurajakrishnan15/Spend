"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

export const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/transactions", label: "Transactions" },
  { href: "/forecasts", label: "Forecasts" },
  { href: "/segments", label: "Segments" },
  { href: "/merchants", label: "Merchants" },
  { href: "/campaigns", label: "Campaigns" },
  { href: "/ops-forecast", label: "Operations" },
  { href: "/budget", label: "Budget" },
  { href: "/macro", label: "Macro" },
  { href: "/sql", label: "SQL Explorer" },
  { href: "/governance", label: "Governance" },
];

export function Logo({ dark = false }: { dark?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="7" fill={dark ? "#ffffff" : "#0b1f3a"} />
        <path d="M7 22 L13 15 L18 19 L25 9" fill="none" stroke={dark ? "#0b1f3a" : "#ffffff"} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="25" cy="9" r="2.4" fill="#b8893a" />
      </svg>
      <span className={`text-lg font-semibold tracking-tight ${dark ? "text-white" : "text-navy-900"}`}>
        Spend<span className="text-navy-400">IQ</span>
      </span>
    </span>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b border-navy-100 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" aria-label="SpendIQ home"><Logo /></Link>
        <nav aria-label="Primary" className="hidden items-center gap-1 xl:flex">
          {NAV.map((n) => {
            const active = pathname === n.href;
            return (
              <Link key={n.href} href={n.href} aria-current={active ? "page" : undefined}
                className={`rounded-md px-2.5 py-2 text-sm font-medium transition-colors ${active ? "bg-navy-900 text-white" : "text-navy-700 hover:bg-navy-50"}`}>
                {n.label}
              </Link>
            );
          })}
        </nav>
        <button type="button" className="rounded-md p-2 text-navy-900 hover:bg-navy-50 xl:hidden"
          aria-expanded={open} aria-controls="mobile-nav" aria-label="Toggle navigation" onClick={() => setOpen((o) => !o)}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
      </div>
      {open && (
        <nav id="mobile-nav" aria-label="Mobile" className="border-t border-navy-100 bg-white px-4 py-3 xl:hidden">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} onClick={() => setOpen(false)}
              className={`block rounded-md px-3 py-2.5 text-sm font-medium ${pathname === n.href ? "bg-navy-900 text-white" : "text-navy-800"}`}>
              {n.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-auto bg-navy-950 text-navy-200">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-3 lg:px-8">
        <div>
          <Logo dark />
          <p className="mt-3 text-sm leading-relaxed text-navy-300">
            Banking customer intelligence and spending forecasting — an educational portfolio project.
          </p>
        </div>
        <div className="text-sm">
          <p className="font-semibold text-white">Explore</p>
          <ul className="mt-3 grid grid-cols-2 gap-2">
            {NAV.map((n) => <li key={n.href}><Link href={n.href} className="hover:text-white">{n.label}</Link></li>)}
          </ul>
        </div>
        <p className="text-xs leading-relaxed text-navy-300">
          All data is synthetic and generated locally. SpendIQ is an independent project: it is not affiliated with, endorsed
          by, or a product of any bank, and it makes no claim of regulatory compliance. Results are illustrative and must not
          be used for credit, eligibility or other decisions about people.
        </p>
      </div>
    </footer>
  );
}
