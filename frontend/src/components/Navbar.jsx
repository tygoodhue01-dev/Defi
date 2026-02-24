import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ConnectButton } from '@rainbow-me/rainbowkit';
import { useAccount, useChainId, useSwitchChain } from 'wagmi';
import { base, baseSepolia } from 'wagmi/chains';
import { Vault, Settings, ExternalLink, Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export function Navbar() {
  const location = useLocation();
  const { isConnected } = useAccount();
  const chainId = useChainId();
  const { switchChain, isPending } = useSwitchChain();
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

  const isActive = (path) => location.pathname === path || location.pathname.startsWith(path + '/');

  const navLinks = [
    { path: '/vaults', label: 'Vaults', icon: Vault },
  ];

  return (
    <header className="sticky top-0 z-50 glass border-b border-border/50">
      <div className="max-w-7xl mx-auto px-4 md:px-8">
        <div className="flex items-center justify-between h-16 md:h-20">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 group" data-testid="navbar-logo">
            <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center glow-primary group-hover:glow-primary-hover transition-all">
              <Vault className="w-5 h-5 text-primary" />
            </div>
            <span className="text-xl font-bold font-heading hidden sm:block">
              <span className="text-primary">Base</span>
              <span className="text-foreground">Vault</span>
            </span>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-2">
            {navLinks.map(({ path, label, icon: Icon }) => (
              <Link key={path} to={path}>
                <Button
                  variant={isActive(path) ? 'secondary' : 'ghost'}
                  className={`gap-2 ${isActive(path) ? 'bg-primary/20 text-primary' : ''}`}
                  data-testid={`nav-${label.toLowerCase()}`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </Button>
              </Link>
            ))}
          </nav>

          {/* Right Side Actions */}
          <div className="flex items-center gap-3">
            {/* Network Switcher */}
            {isConnected && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="hidden sm:flex gap-2 border-border/50 hover:border-primary/50"
                    data-testid="network-switcher"
                    disabled={isPending}
                  >
                    <div className={`w-2 h-2 rounded-full ${chainId === base.id ? 'bg-green-500' : 'bg-yellow-500'}`} />
                    {chainId === base.id ? 'Base' : 'Sepolia'}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="bg-card border-border">
                  <DropdownMenuItem
                    onClick={() => switchChain({ chainId: base.id })}
                    className={chainId === base.id ? 'bg-primary/10' : ''}
                    data-testid="switch-base-mainnet"
                  >
                    <div className="w-2 h-2 rounded-full bg-green-500 mr-2" />
                    Base Mainnet
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => switchChain({ chainId: baseSepolia.id })}
                    className={chainId === baseSepolia.id ? 'bg-primary/10' : ''}
                    data-testid="switch-base-sepolia"
                  >
                    <div className="w-2 h-2 rounded-full bg-yellow-500 mr-2" />
                    Base Sepolia
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}

            {/* Connect Button */}
            <div data-testid="connect-wallet-btn">
              <ConnectButton 
                chainStatus="icon"
                showBalance={false}
                accountStatus={{
                  smallScreen: 'avatar',
                  largeScreen: 'full',
                }}
              />
            </div>

            {/* Admin Link */}
            <Link to="/admin/vaults" className="hidden md:block">
              <Button variant="ghost" size="icon" data-testid="admin-link">
                <Settings className="w-4 h-4" />
              </Button>
            </Link>

            {/* Mobile Menu Button */}
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              data-testid="mobile-menu-btn"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </Button>
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden py-4 border-t border-border/50">
            <nav className="flex flex-col gap-2">
              {navLinks.map(({ path, label, icon: Icon }) => (
                <Link key={path} to={path} onClick={() => setMobileMenuOpen(false)}>
                  <Button
                    variant={isActive(path) ? 'secondary' : 'ghost'}
                    className={`w-full justify-start gap-2 ${isActive(path) ? 'bg-primary/20 text-primary' : ''}`}
                  >
                    <Icon className="w-4 h-4" />
                    {label}
                  </Button>
                </Link>
              ))}
              <Link to="/admin/vaults" onClick={() => setMobileMenuOpen(false)}>
                <Button variant="ghost" className="w-full justify-start gap-2">
                  <Settings className="w-4 h-4" />
                  Admin
                </Button>
              </Link>
            </nav>
          </div>
        )}
      </div>
    </header>
  );
}
