import React from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { SITE_NAME } from "../constants";

const LINKS = [
  ["/results", "Results"],
  ["/bets", "Bet log"],
  ["/methodology", "Methodology"],
];

const linkClass = ({ isActive }) =>
  `text-sm font-medium ${isActive ? "text-ink" : "text-ink-2 hover:text-ink"}`;

export default function Navbar() {
  const { search } = useLocation();
  return (
    <header className="sticky top-0 z-10 border-b border-hairline bg-ground/90 backdrop-blur">
      <div className="mx-auto flex max-w-content items-center justify-between px-6 py-4">
        <Link to="/" className="font-display text-2xl font-bold uppercase tracking-wide text-ink">
          {SITE_NAME}
        </Link>
        <nav className="flex items-center gap-6" aria-label="Primary">
          <div className="hidden items-center gap-6 sm:flex">
            {LINKS.map(([to, label]) => (
              <NavLink key={to} to={{ pathname: to, search }} className={linkClass}>
                {label}
              </NavLink>
            ))}
          </div>
          <Link
            to="/join"
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-hover"
          >
            Get the picks
          </Link>
        </nav>
      </div>
      <nav className="flex gap-5 px-6 pb-3 sm:hidden" aria-label="Primary, compact">
        {LINKS.map(([to, label]) => (
          <NavLink key={to} to={{ pathname: to, search }} className={linkClass}>
            {label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
