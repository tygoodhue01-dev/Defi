import React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, Clock, Wallet, ExternalLink, Pause, AlertTriangle, XCircle } from 'lucide-react';
import { formatUSD, formatPercent, formatTimeAgo } from '@/lib/utils';
import { chainNames } from '@/lib/wagmi';

function DataQualityBadge({ quality }) {
  if (!quality || quality === 'ok') return null;
  if (quality === 'stale') {
    return (
      <Badge variant="outline" className="border-yellow-500/50 text-yellow-400 bg-yellow-500/10 gap-1 text-[10px]" data-testid="data-quality-badge">
        <AlertTriangle className="w-3 h-3" />
        Stale
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="border-red-500/50 text-red-400 bg-red-500/10 gap-1 text-[10px]" data-testid="data-quality-badge">
      <XCircle className="w-3 h-3" />
      Error
    </Badge>
  );
}

export function VaultCard({ vault, tvl, apy }) {
  const isPaused = vault.paused;
  const isExperimental = vault.experimental;

  const tvlValue = tvl?.tvl || 0;
  const apyValue = apy?.totalApy || 0;
  const dataQuality = tvl?.dataQuality === 'error' || apy?.dataQuality === 'error'
    ? 'error'
    : tvl?.dataQuality === 'stale' || apy?.dataQuality === 'stale'
      ? 'stale'
      : 'ok';

  return (
    <Link to={`/vaults/${vault.id}`} data-testid={`vault-card-${vault.id}`}>
      <Card className="group bg-card border-border hover:border-primary/50 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,82,255,0.15)] overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                <span className="text-lg font-bold text-primary">
                  {vault.token0?.slice(0, 1)}{vault.token1?.slice(0, 1)}
                </span>
              </div>
              <div>
                <CardTitle className="text-lg font-bold text-foreground group-hover:text-primary transition-colors">
                  {vault.name}
                </CardTitle>
                <p className="text-sm text-muted-foreground font-mono">
                  {vault.token0}/{vault.token1}
                </p>
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              <div className="flex gap-1 flex-wrap justify-end">
                {isPaused ? (
                  <Badge variant="destructive" className="gap-1">
                    <Pause className="w-3 h-3" />
                    Paused
                  </Badge>
                ) : (
                  <Badge variant="secondary" className="bg-green-500/20 text-green-400 border-green-500/30">
                    Active
                  </Badge>
                )}
                {isExperimental && (
                  <Badge variant="outline" className="border-yellow-500/50 text-yellow-400 bg-yellow-500/10">
                    Beta
                  </Badge>
                )}
                <DataQualityBadge quality={dataQuality} />
              </div>
              <span className="text-xs text-muted-foreground">
                {chainNames[vault.chainId] || `Chain ${vault.chainId}`}
              </span>
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-0">
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Wallet className="w-3 h-3" />
                TVL
              </div>
              <p className="text-lg font-bold font-mono text-foreground" data-testid="vault-card-tvl">
                {formatUSD(tvlValue)}
              </p>
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <TrendingUp className="w-3 h-3" />
                APY
              </div>
              <p className="text-lg font-bold font-mono text-green-400" data-testid="vault-card-apy">
                {apy?.totalApy != null ? formatPercent(apyValue) : '-'}
              </p>
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="w-3 h-3" />
                Harvest
              </div>
              <p className="text-sm font-medium text-foreground">
                -
              </p>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-border/50 flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-mono">
              {vault.vaultAddress?.slice(0, 10)}...
            </span>
            <span className="text-xs text-primary flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              View Details <ExternalLink className="w-3 h-3" />
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
