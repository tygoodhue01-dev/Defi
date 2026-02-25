import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAccount, useChainId, useReadContract } from 'wagmi';
import { toast } from 'sonner';
import {
  ArrowLeft,
  ExternalLink,
  Loader2,
  RefreshCw,
  Wallet,
  TrendingUp,
  Clock,
  Copy,
  Check,
  AlertCircle,
  Pause,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { VaultActions } from '@/components/VaultActions';
import { HarvestHistory } from '@/components/HarvestHistory';
import { vaultApi, metricsApi, harvestApi, beefyApi } from '@/lib/api';
import { VAULT_ABI, ERC20_ABI } from '@/lib/contracts';
import {
  formatUSD,
  formatPercent,
  formatTimeAgo,
  formatDateTime,
  formatAddress,
  formatFromWei,
} from '@/lib/utils';
import { chainNames } from '@/lib/wagmi';

export default function VaultDetailPage() {
  const { id } = useParams();
  const { address, isConnected } = useAccount();
  const chainId = useChainId();
  const [vault, setVault] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [apyBreakdown, setApyBreakdown] = useState(null);
  const [harvests, setHarvests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [copiedField, setCopiedField] = useState(null);

  // Read on-chain data
  const { data: pricePerShare, refetch: refetchPrice } = useReadContract({
    address: vault?.vaultAddress,
    abi: VAULT_ABI,
    functionName: 'pricePerShare',
    query: { enabled: !!vault?.vaultAddress },
  });

  const { data: totalAssets, refetch: refetchAssets } = useReadContract({
    address: vault?.vaultAddress,
    abi: VAULT_ABI,
    functionName: 'totalAssets',
    query: { enabled: !!vault?.vaultAddress },
  });

  const { data: userShares, refetch: refetchUserShares } = useReadContract({
    address: vault?.vaultAddress,
    abi: VAULT_ABI,
    functionName: 'balanceOf',
    args: [address],
    query: { enabled: !!vault?.vaultAddress && !!address },
  });

  const { data: userLpBalance, refetch: refetchUserLp } = useReadContract({
    address: vault?.wantAddress,
    abi: ERC20_ABI,
    functionName: 'balanceOf',
    args: [address],
    query: { enabled: !!vault?.wantAddress && !!address },
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      const [vaultData, metricsData, harvestsData, apyData] = await Promise.all([
        vaultApi.getVault(id),
        metricsApi.getMetrics(id),
        harvestApi.getHarvests(id),
        beefyApi.getVaultApy(id),
      ]);
      setVault(vaultData);
      setMetrics(metricsData);
      setHarvests(harvestsData);
      setApyBreakdown(apyData);
    } catch (e) {
      console.error('Failed to fetch vault:', e);
      toast.error('Failed to load vault details');
    } finally {
      setLoading(false);
    }
  };

  const refreshMetrics = async () => {
    try {
      setRefreshing(true);
      const [newMetrics, newApy] = await Promise.all([
        metricsApi.refreshMetrics(id),
        beefyApi.getVaultApy(id),
      ]);
      setMetrics(newMetrics);
      setApyBreakdown(newApy);
      refetchPrice();
      refetchAssets();
      toast.success('Metrics refreshed');
    } catch (e) {
      console.error('Failed to refresh metrics:', e);
      toast.error('Failed to refresh metrics');
    } finally {
      setRefreshing(false);
    }
  };

  const handleActionComplete = () => {
    refetchUserShares();
    refetchUserLp();
    refetchAssets();
    refreshMetrics();
  };

  const copyToClipboard = (text, field) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  useEffect(() => {
    if (id) fetchData();
  }, [id]);

  const getExplorerUrl = (addr) => {
    const base = vault?.chainId === 8453 
      ? 'https://basescan.org/address/' 
      : 'https://sepolia.basescan.org/address/';
    return `${base}${addr}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!vault) {
    return (
      <div className="max-w-7xl mx-auto px-4 md:px-8 py-12">
        <div className="text-center py-20">
          <AlertCircle className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
          <h2 className="text-2xl font-bold mb-2">Vault Not Found</h2>
          <p className="text-muted-foreground mb-6">
            The vault you're looking for doesn't exist or has been removed.
          </p>
          <Link to="/vaults">
            <Button>
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Vaults
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const formattedPricePerShare = pricePerShare ? formatFromWei(pricePerShare.toString()) : metrics?.pricePerShare || '1';
  const formattedTotalAssets = totalAssets ? formatFromWei(totalAssets.toString()) : '0';
  const formattedUserShares = userShares ? formatFromWei(userShares.toString()) : '0';
  const formattedUserLp = userLpBalance ? formatFromWei(userLpBalance.toString()) : '0';

  // Calculate deposited LP value from shares
  const depositedLpValue = userShares && pricePerShare
    ? (Number(userShares) * Number(pricePerShare)) / 1e36
    : 0;

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 py-8 md:py-12" data-testid="vault-detail-page">
      {/* Header */}
      <div className="mb-8">
        <Link to="/vaults" className="inline-flex items-center text-muted-foreground hover:text-foreground mb-4 transition-colors">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Vaults
        </Link>
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
              <span className="text-2xl font-bold text-primary">
                {vault.token0?.slice(0, 1)}{vault.token1?.slice(0, 1)}
              </span>
            </div>
            <div>
              <h1 className="text-3xl md:text-4xl font-bold" data-testid="vault-name">{vault.name}</h1>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-muted-foreground font-mono">
                  {vault.token0}/{vault.token1}
                </span>
                <Badge variant="outline" className="text-xs">
                  {chainNames[vault.chainId]}
                </Badge>
                {vault.paused && (
                  <Badge variant="destructive" className="gap-1">
                    <Pause className="w-3 h-3" />
                    Paused
                  </Badge>
                )}
                {vault.experimental && (
                  <Badge variant="outline" className="border-yellow-500/50 text-yellow-400 bg-yellow-500/10">
                    Beta
                  </Badge>
                )}
                {apyBreakdown?.dataQuality && apyBreakdown.dataQuality !== 'ok' && (
                  <Badge 
                    variant="outline" 
                    className={apyBreakdown.dataQuality === 'stale' 
                      ? 'border-yellow-500/50 text-yellow-400 bg-yellow-500/10 gap-1' 
                      : 'border-red-500/50 text-red-400 bg-red-500/10 gap-1'}
                    data-testid="data-quality-badge"
                  >
                    <AlertCircle className="w-3 h-3" />
                    {apyBreakdown.dataQuality === 'stale' ? 'Stale Data' : 'Data Error'}
                  </Badge>
                )}
              </div>
            </div>
          </div>
          
          <Button
            onClick={refreshMetrics}
            disabled={refreshing}
            variant="outline"
            className="gap-2"
            data-testid="refresh-metrics-btn"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh Metrics
          </Button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column - Metrics & Details */}
        <div className="lg:col-span-7 space-y-6">
          {/* Key Metrics */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle>Vault Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                <MetricBox
                  icon={Wallet}
                  label="TVL"
                  value={formatUSD(metrics?.tvl || 0)}
                  testId="vault-tvl"
                />
                <MetricBox
                  icon={TrendingUp}
                  label="Total APY"
                  value={apyBreakdown?.totalApy != null ? formatPercent(apyBreakdown.totalApy) : formatPercent(metrics?.apy || 0)}
                  valueClass="text-green-400"
                  testId="vault-apy"
                />
                <MetricBox
                  icon={Clock}
                  label="Last Harvest"
                  value={formatTimeAgo(metrics?.lastHarvestAt)}
                  testId="vault-last-harvest"
                />
                <MetricBox
                  label="Price/Share"
                  value={formattedPricePerShare}
                  mono
                  testId="vault-price-per-share"
                />
              </div>
            </CardContent>
          </Card>

          {/* APY Breakdown */}
          {apyBreakdown && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  APY Breakdown
                  {apyBreakdown.dataQuality && apyBreakdown.dataQuality !== 'ok' && (
                    <Badge 
                      variant="outline"
                      className={apyBreakdown.dataQuality === 'stale' 
                        ? 'border-yellow-500/50 text-yellow-400 bg-yellow-500/10 text-[10px]' 
                        : 'border-red-500/50 text-red-400 bg-red-500/10 text-[10px]'}
                    >
                      {apyBreakdown.dataQuality}
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <InfoRow label="Vault APR (net)" value={apyBreakdown.vaultApr != null ? formatPercent(apyBreakdown.vaultApr) : '-'} />
                <InfoRow label="Vault APY (compounded)" value={apyBreakdown.vaultApy != null ? formatPercent(apyBreakdown.vaultApy) : '-'} />
                <InfoRow label="Trading APR" value={apyBreakdown.tradingApr != null ? formatPercent(apyBreakdown.tradingApr) : '-'} />
                <Separator />
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Total APY</span>
                  <span className="text-sm font-bold text-green-400" data-testid="vault-total-apy">
                    {apyBreakdown.totalApy != null ? formatPercent(apyBreakdown.totalApy) : '-'}
                  </span>
                </div>
                <Separator />
                <InfoRow label="Compoundings/Year" value={apyBreakdown.compoundingsPerYear?.toLocaleString() || '-'} mono />
                <InfoRow label="Performance Fee" value={apyBreakdown.beefyPerformanceFee != null ? `${(apyBreakdown.beefyPerformanceFee * 100).toFixed(1)}%` : '-'} />
              </CardContent>
            </Card>
          )}

          {/* Your Position */}
          {isConnected && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle>Your Position</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="p-4 rounded-lg bg-muted/30">
                    <p className="text-sm text-muted-foreground mb-1">LP Balance</p>
                    <p className="text-xl font-bold font-mono" data-testid="user-lp-balance">
                      {formattedUserLp}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-muted/30">
                    <p className="text-sm text-muted-foreground mb-1">Vault Shares</p>
                    <p className="text-xl font-bold font-mono" data-testid="user-vault-shares">
                      {formattedUserShares}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-primary/10 border border-primary/20">
                    <p className="text-sm text-muted-foreground mb-1">Deposited Value</p>
                    <p className="text-xl font-bold font-mono text-primary" data-testid="user-deposited-value">
                      {depositedLpValue.toFixed(4)} LP
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Contract Addresses */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle>Contract Addresses</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <AddressRow
                label="Vault"
                address={vault.vaultAddress}
                explorerUrl={getExplorerUrl(vault.vaultAddress)}
                copied={copiedField === 'vault'}
                onCopy={() => copyToClipboard(vault.vaultAddress, 'vault')}
                testId="vault-address"
              />
              <Separator />
              <AddressRow
                label="Strategy"
                address={vault.strategyAddress}
                explorerUrl={getExplorerUrl(vault.strategyAddress)}
                copied={copiedField === 'strategy'}
                onCopy={() => copyToClipboard(vault.strategyAddress, 'strategy')}
                testId="strategy-address"
              />
              <Separator />
              <AddressRow
                label="Want Token (LP)"
                address={vault.wantAddress}
                explorerUrl={getExplorerUrl(vault.wantAddress)}
                copied={copiedField === 'want'}
                onCopy={() => copyToClipboard(vault.wantAddress, 'want')}
                testId="want-address"
              />
            </CardContent>
          </Card>

          {/* Harvest History */}
          <HarvestHistory harvests={harvests} chainId={vault.chainId} />
        </div>

        {/* Right Column - Actions */}
        <div className="lg:col-span-5 space-y-6">
          <VaultActions vault={vault} onActionComplete={handleActionComplete} />
          
          {/* Vault Info */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle>Vault Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <InfoRow label="Total Assets" value={`${formattedTotalAssets}`} mono />
              <InfoRow label="Token 0" value={vault.token0} />
              <InfoRow label="Token 1" value={vault.token1} />
              <InfoRow label="Reward Token" value={vault.rewardToken} />
              <InfoRow label="Last Updated" value={formatDateTime(metrics?.updatedAt)} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function MetricBox({ icon: Icon, label, value, valueClass = '', mono = false, testId }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1 text-sm text-muted-foreground">
        {Icon && <Icon className="w-4 h-4" />}
        {label}
      </div>
      <p className={`text-2xl font-bold ${mono ? 'font-mono' : ''} ${valueClass}`} data-testid={testId}>
        {value}
      </p>
    </div>
  );
}

function AddressRow({ label, address, explorerUrl, copied, onCopy, testId }) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="font-mono text-sm" data-testid={testId}>{formatAddress(address)}</p>
      </div>
      <div className="flex gap-2">
        <Button variant="ghost" size="icon" onClick={onCopy}>
          {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
        </Button>
        <a href={explorerUrl} target="_blank" rel="noopener noreferrer">
          <Button variant="ghost" size="icon">
            <ExternalLink className="w-4 h-4" />
          </Button>
        </a>
      </div>
    </div>
  );
}

function InfoRow({ label, value, mono = false }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-sm ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  );
}
