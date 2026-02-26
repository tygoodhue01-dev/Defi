import React, { useState, useEffect } from 'react';
import { useChainId } from 'wagmi';
import { Loader2, Search, RefreshCw, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { VaultCard } from '@/components/VaultCard';
import { vaultApi, beefyApi } from '@/lib/api';
import { chainNames } from '@/lib/wagmi';

function normalizeVaults(data) {
  if (Array.isArray(data)) return data;
  if (!data || typeof data !== 'object') return [];
  if (Array.isArray(data.vaults)) return data.vaults;
  if (Array.isArray(data.data)) return data.data;
  if (Array.isArray(data.items)) return data.items;
  if (Array.isArray(data.results)) return data.results;
  return [];
}

function safeLower(x) {
  return (typeof x === 'string' ? x : '').toLowerCase();
}

export default function VaultsPage() {
  const chainId = useChainId();
  const [vaults, setVaults] = useState([]);
  const [tvlData, setTvlData] = useState({});
  const [apyData, setApyData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [chainFilter, setChainFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

const fetchVaults = async () => {
  try {
    setLoading(true);
    setError(null);

    // Don't let 1 failed request kill the whole page
    const results = await Promise.allSettled([
      vaultApi.getVaults(),
      beefyApi.getTvl(),
      beefyApi.getApy(),
    ]);

    const vaultsResult = results[0];
    const tvlResult = results[1];
    const apyResult = results[2];

    const vaultList =
      vaultsResult.status === "fulfilled"
        ? vaultsResult.value
        : [];

    const tvl =
      tvlResult.status === "fulfilled"
        ? tvlResult.value
        : {};

    const apy =
      apyResult.status === "fulfilled"
        ? apyResult.value
        : {};

    // Vaults are required
    if (!Array.isArray(vaultList)) {
      console.error("getVaults() did not return an array:", vaultList);
      setVaults([]);
      setError("Vaults API returned unexpected data.");
      return;
    }

    setVaults(vaultList);
    setTvlData(tvl || {});
    setApyData(apy || {});

    // Optional: show a softer warning if Beefy fails
    if (tvlResult.status === "rejected" || apyResult.status === "rejected") {
      console.warn("Beefy data failed (TVL/APY). Vaults still loaded.", {
        tvlError: tvlResult.status === "rejected" ? tvlResult.reason : null,
        apyError: apyResult.status === "rejected" ? apyResult.reason : null,
      });
    }
  } catch (e) {
    console.error("Failed to fetch vaults:", e);
    setError("Failed to load vaults. Please try again.");
  } finally {
    setLoading(false);
  }
};

  useEffect(() => {
    fetchVaults();
  }, []);

  const filteredVaults = (Array.isArray(vaults) ? vaults : []).filter((vault) => {
    const q = safeLower(searchQuery);

    const matchesSearch =
      q.length === 0 ||
      safeLower(vault?.name).includes(q) ||
      safeLower(vault?.token0).includes(q) ||
      safeLower(vault?.token1).includes(q);

    const vaultChainId =
      typeof vault?.chainId === 'number' ? vault.chainId : parseInt(vault?.chainId, 10);

    const matchesChain =
      chainFilter === 'all' ||
      (Number.isFinite(vaultChainId) && vaultChainId === parseInt(chainFilter, 10));

    const paused = Boolean(vault?.paused);

    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'active' && !paused) ||
      (statusFilter === 'paused' && paused);

    return matchesSearch && matchesChain && matchesStatus;
  });

  // Calculate totals from Beefy-style TVL data (safe even if tvlData isn't perfect)
  const totalTvl = Object.entries(tvlData || {})
    .filter(([k]) => k !== '_meta')
    .reduce((sum, [, v]) => sum + (v?.tvl || 0), 0);

  const activeCount = (Array.isArray(vaults) ? vaults : []).filter((v) => !v?.paused).length;

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 py-8 md:py-12">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-4xl md:text-5xl font-bold mb-4" data-testid="vaults-title">
          Vaults
        </h1>
        <p className="text-muted-foreground text-lg">
          Deposit your LP tokens and earn auto-compounding yield
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <div className="p-6 rounded-xl bg-card border border-border">
          <p className="text-sm text-muted-foreground mb-1">Total Value Locked</p>
          <p className="text-3xl font-bold font-mono text-foreground" data-testid="total-tvl">
            ${Number(totalTvl || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </p>
        </div>

        <div className="p-6 rounded-xl bg-card border border-border">
          <p className="text-sm text-muted-foreground mb-1">Active Vaults</p>
          <p
            className="text-3xl font-bold font-mono text-foreground"
            data-testid="active-vaults-count"
          >
            {activeCount}
          </p>
        </div>

        <div className="p-6 rounded-xl bg-card border border-border">
          <p className="text-sm text-muted-foreground mb-1">Your Network</p>
          <p className="text-3xl font-bold text-primary" data-testid="current-network">
            {chainNames[chainId] || 'Not Connected'}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4 mb-8">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search vaults..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 h-11"
            data-testid="vault-search-input"
          />
        </div>

        <Select value={chainFilter} onValueChange={setChainFilter}>
          <SelectTrigger className="w-full md:w-[180px] h-11" data-testid="chain-filter">
            <SelectValue placeholder="All Chains" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Chains</SelectItem>
            <SelectItem value="8453">Base Mainnet</SelectItem>
            <SelectItem value="84532">Base Sepolia</SelectItem>
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full md:w-[180px] h-11" data-testid="status-filter">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="paused">Paused</SelectItem>
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          onClick={fetchVaults}
          disabled={loading}
          className="h-11 gap-2"
          data-testid="refresh-vaults-btn"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <AlertCircle className="w-12 h-12 text-destructive mb-4" />
          <p className="text-destructive mb-4">{error}</p>
          <Button onClick={fetchVaults} variant="outline">
            Try Again
          </Button>
        </div>
      ) : filteredVaults.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
            <Search className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-xl font-semibold mb-2">No Vaults Found</h3>
          <p className="text-muted-foreground max-w-md">
            {(Array.isArray(vaults) ? vaults.length : 0) === 0
              ? 'No vaults have been created yet. Check back later or create one in the admin panel.'
              : 'No vaults match your current filters. Try adjusting your search criteria.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="vaults-grid">
          {filteredVaults.map((vault) => (
            <VaultCard
              key={vault?.id ?? `${vault?.name ?? 'vault'}-${vault?.chainId ?? 'na'}`}
              vault={vault}
              tvl={tvlData?.[vault?.id]}
              apy={apyData?.[vault?.id]}
            />
          ))}
        </div>
      )}
    </div>
  );
}