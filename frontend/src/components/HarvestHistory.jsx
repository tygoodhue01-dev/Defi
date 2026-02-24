import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ExternalLink, Clock } from 'lucide-react';
import { formatTimeAgo, formatFromWei, formatAddress } from '@/lib/utils';

export function HarvestHistory({ harvests, chainId }) {
  const explorerUrl = chainId === 8453 
    ? 'https://basescan.org/tx/' 
    : 'https://sepolia.basescan.org/tx/';

  if (!harvests || harvests.length === 0) {
    return (
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Harvest History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm text-center py-8">
            No harvest events recorded yet
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card border-border" data-testid="harvest-history">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Clock className="w-5 h-5" />
          Harvest History
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[300px] pr-4">
          <div className="space-y-3">
            {harvests.map((harvest, index) => (
              <div
                key={harvest.id || index}
                className="flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
                data-testid={`harvest-event-${index}`}
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs font-mono">
                      {formatTimeAgo(harvest.harvestAt)}
                    </Badge>
                    {harvest.profit && harvest.profit !== '0' && (
                      <Badge className="bg-green-500/20 text-green-400 border-green-500/30 text-xs">
                        +{formatFromWei(harvest.profit)}
                      </Badge>
                    )}
                  </div>
                  <a
                    href={`${explorerUrl}${harvest.txHash}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-mono text-muted-foreground hover:text-primary flex items-center gap-1"
                  >
                    {formatAddress(harvest.txHash)}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
