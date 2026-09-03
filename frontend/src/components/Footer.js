import React from "react";
import { Link } from "react-router-dom";
import { GITHUB_URL, RESPONSIBLE_GAMBLING_URL, SITE_NAME } from "../constants";

export default function Footer() {
  return (
    <footer className="mt-24 border-t border-hairline">
      <div className="mx-auto max-w-content px-6 py-10 text-sm text-ink-2">
        <p className="max-w-3xl">
          {SITE_NAME} publishes model output for informational purposes. Nothing here is betting
          advice. Past performance does not guarantee future results. Every bankroll figure on this
          site is a $1,000 paper bankroll replayed against closing odds. You must be of legal
          gambling age in your jurisdiction.
        </p>
        <div className="mt-6 flex flex-wrap gap-6 text-muted">
          <a href={RESPONSIBLE_GAMBLING_URL} target="_blank" rel="noreferrer" className="hover:text-ink">
            Gambling problem? Get help
          </a>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hover:text-ink">
            Source on GitHub
          </a>
          <Link to="/methodology" className="hover:text-ink">
            Methodology
          </Link>
        </div>
      </div>
    </footer>
  );
}
