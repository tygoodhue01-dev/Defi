import React from 'react';
import { Github, Twitter, ExternalLink } from 'lucide-react';

// SVG Logo Component
const VaultLogo = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
);

export function Footer() {
  return (
    <footer className="border-t border-border/50 bg-card/30">
      <div className="max-w-7xl mx-auto px-4 md:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="md:col-span-2">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
                <VaultLogo className="w-5 h-5 text-primary" />
              </div>
              <span className="text-xl font-bold">
                <span className="text-primary">Base</span>
                <span className="text-foreground">Vault</span>
              </span>
            </div>
            <p className="text-muted-foreground text-sm max-w-sm">
              Automated yield optimization on Base. Deposit your LP tokens and let our strategies 
              compound your rewards automatically.
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="font-semibold mb-4 text-foreground">Resources</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="https://docs.base.org" target="_blank" rel="noopener noreferrer" 
                   className="text-muted-foreground hover:text-primary transition-colors flex items-center gap-1">
                  Documentation <ExternalLink className="w-3 h-3" />
                </a>
              </li>
              <li>
                <a href="https://basescan.org" target="_blank" rel="noopener noreferrer"
                   className="text-muted-foreground hover:text-primary transition-colors flex items-center gap-1">
                  BaseScan <ExternalLink className="w-3 h-3" />
                </a>
              </li>
            </ul>
          </div>

          {/* Social */}
          <div>
            <h4 className="font-semibold mb-4 text-foreground">Community</h4>
            <div className="flex gap-3">
              <a href="#" className="w-9 h-9 rounded-lg bg-muted flex items-center justify-center text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors">
                <Twitter className="w-4 h-4" />
              </a>
              <a href="#" className="w-9 h-9 rounded-lg bg-muted flex items-center justify-center text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors">
                <Github className="w-4 h-4" />
              </a>
            </div>
          </div>
        </div>

        <div className="mt-12 pt-6 border-t border-border/50 flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} BaseVault. All rights reserved.</p>
          <p className="font-mono text-xs">Built on Base</p>
        </div>
      </div>
    </footer>
  );
}
