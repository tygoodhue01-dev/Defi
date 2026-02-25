import React, { useState, useEffect } from 'react';
import { useAccount, useReadContract, useWriteContract, useWaitForTransactionReceipt } from 'wagmi';
import { parseUnits, formatUnits } from 'viem';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Loader2, ArrowDown, ArrowUp, AlertCircle, RotateCcw } from 'lucide-react';
import { ERC20_ABI, VAULT_ABI } from '@/lib/contracts';
import { userActionApi } from '@/lib/api';

export function VaultActions({ vault, onActionComplete }) {
  const { address, isConnected } = useAccount();
  const [depositAmount, setDepositAmount] = useState('');
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [activeTab, setActiveTab] = useState('deposit');
  const [decimals, setDecimals] = useState(18);
  const [withdrawMode, setWithdrawMode] = useState('shares'); // 'shares' or 'lp'

  const vaultAddress = vault.vaultAddress;
  const wantAddress = vault.wantAddress;

  // Read LP token decimals
  const { data: tokenDecimals } = useReadContract({
    address: wantAddress,
    abi: ERC20_ABI,
    functionName: 'decimals',
    query: { enabled: !!wantAddress },
  });

  // Read price per share for LP conversion
  const { data: pricePerShare } = useReadContract({
    address: vaultAddress,
    abi: VAULT_ABI,
    functionName: 'pricePerShare',
    query: { enabled: !!vaultAddress },
  });

  // Update decimals when fetched
  useEffect(() => {
    if (tokenDecimals !== undefined) {
      setDecimals(Number(tokenDecimals));
    }
  }, [tokenDecimals]);

  // Read LP token balance
  const { data: lpBalance, refetch: refetchLpBalance } = useReadContract({
    address: wantAddress,
    abi: ERC20_ABI,
    functionName: 'balanceOf',
    args: [address],
    query: { enabled: !!address && isConnected && !!wantAddress },
  });

  // Read vault share balance
  const { data: shareBalance, refetch: refetchShareBalance } = useReadContract({
    address: vaultAddress,
    abi: VAULT_ABI,
    functionName: 'balanceOf',
    args: [address],
    query: { enabled: !!address && isConnected && !!vaultAddress },
  });

  // Read allowance
  const { data: allowance, refetch: refetchAllowance } = useReadContract({
    address: wantAddress,
    abi: ERC20_ABI,
    functionName: 'allowance',
    args: [address, vaultAddress],
    query: { enabled: !!address && isConnected && !!wantAddress && !!vaultAddress },
  });

  // Write contracts
  const { writeContract: approve, data: approveHash, isPending: isApproving } = useWriteContract();
  const { writeContract: deposit, data: depositHash, isPending: isDepositing } = useWriteContract();
  const { writeContract: withdraw, data: withdrawHash, isPending: isWithdrawing } = useWriteContract();

  // Wait for transactions
  const { isLoading: isApproveConfirming, isSuccess: isApproveSuccess } = useWaitForTransactionReceipt({ hash: approveHash });
  const { isLoading: isDepositConfirming, isSuccess: isDepositSuccess } = useWaitForTransactionReceipt({ hash: depositHash });
  const { isLoading: isWithdrawConfirming, isSuccess: isWithdrawSuccess } = useWaitForTransactionReceipt({ hash: withdrawHash });

  // Handle approval success
  useEffect(() => {
    if (isApproveSuccess) {
      toast.success('Approval successful!');
      refetchAllowance();
    }
  }, [isApproveSuccess, refetchAllowance]);

  // Handle deposit success
  useEffect(() => {
    if (isDepositSuccess && depositHash) {
      toast.success('Deposit successful!');
      refetchLpBalance();
      refetchShareBalance();
      
      userActionApi.recordAction({
        vaultId: vault.id,
        userAddress: address.toLowerCase(),
        actionType: 'deposit',
        amount: parseUnits(depositAmount || '0', decimals).toString(),
        txHash: depositHash,
      }).catch(console.error);
      
      setDepositAmount('');
      onActionComplete?.();
    }
  }, [isDepositSuccess, depositHash]);

  // Handle withdraw success
  useEffect(() => {
    if (isWithdrawSuccess && withdrawHash) {
      toast.success('Withdrawal successful!');
      refetchLpBalance();
      refetchShareBalance();
      
      userActionApi.recordAction({
        vaultId: vault.id,
        userAddress: address.toLowerCase(),
        actionType: 'withdraw',
        amount: withdrawAmount,
        txHash: withdrawHash,
      }).catch(console.error);
      
      setWithdrawAmount('');
      onActionComplete?.();
    }
  }, [isWithdrawSuccess, withdrawHash]);

  // Convert LP amount to shares using pricePerShare
  const lpToShares = (lpAmount) => {
    if (!pricePerShare || pricePerShare === 0n) return 0n;
    try {
      const lpWei = parseUnits(lpAmount, decimals);
      // shares = lpAmount * 1e18 / pricePerShare
      return (lpWei * BigInt(10 ** decimals)) / pricePerShare;
    } catch {
      return 0n;
    }
  };

  // Convert shares to LP amount using pricePerShare
  const sharesToLp = (shares) => {
    if (!pricePerShare) return '0';
    try {
      // lpAmount = shares * pricePerShare / 1e18
      const lpWei = (shares * pricePerShare) / BigInt(10 ** decimals);
      return formatUnits(lpWei, decimals);
    } catch {
      return '0';
    }
  };

  const needsApproval = () => {
    if (!depositAmount || !allowance) return false;
    try {
      const amount = parseUnits(depositAmount, decimals);
      return allowance < amount;
    } catch {
      return false;
    }
  };

  const handleApprove = () => {
    if (!depositAmount) return;
    try {
      const amount = parseUnits(depositAmount, decimals);
      approve({
        address: wantAddress,
        abi: ERC20_ABI,
        functionName: 'approve',
        args: [vaultAddress, amount],
      });
    } catch (error) {
      toast.error('Invalid amount');
    }
  };

  const handleDeposit = () => {
    if (!depositAmount) return;
    try {
      const amount = parseUnits(depositAmount, decimals);
      deposit({
        address: vaultAddress,
        abi: VAULT_ABI,
        functionName: 'deposit',
        args: [amount],
      });
    } catch (error) {
      toast.error('Invalid amount');
    }
  };

  const handleWithdraw = () => {
    if (!withdrawAmount) return;
    try {
      let sharesToWithdraw;
      
      if (withdrawMode === 'lp') {
        // Convert LP amount to shares
        sharesToWithdraw = lpToShares(withdrawAmount);
        if (sharesToWithdraw === 0n) {
          toast.error('Invalid amount or price per share unavailable');
          return;
        }
      } else {
        // Direct shares input
        sharesToWithdraw = parseUnits(withdrawAmount, decimals);
      }
      
      withdraw({
        address: vaultAddress,
        abi: VAULT_ABI,
        functionName: 'withdraw',
        args: [sharesToWithdraw],
      });
    } catch (error) {
      toast.error('Invalid amount');
    }
  };

  const setMaxDeposit = () => {
    if (lpBalance) {
      setDepositAmount(formatUnits(lpBalance, decimals));
    }
  };

  const setMaxWithdraw = () => {
    if (shareBalance) {
      if (withdrawMode === 'lp') {
        // Convert shares to LP value
        setWithdrawAmount(sharesToLp(shareBalance));
      } else {
        setWithdrawAmount(formatUnits(shareBalance, decimals));
      }
    }
  };

  const toggleWithdrawMode = () => {
    setWithdrawAmount('');
    setWithdrawMode(withdrawMode === 'shares' ? 'lp' : 'shares');
  };

  const formattedLpBalance = lpBalance ? formatUnits(lpBalance, decimals) : '0';
  const formattedShareBalance = shareBalance ? formatUnits(shareBalance, decimals) : '0';
  const formattedSharesAsLp = shareBalance ? sharesToLp(shareBalance) : '0';
  
  // Calculate preview of conversion
  const withdrawPreview = withdrawMode === 'lp' && withdrawAmount 
    ? `≈ ${formatUnits(lpToShares(withdrawAmount), decimals)} shares`
    : withdrawMode === 'shares' && withdrawAmount && pricePerShare
    ? `≈ ${sharesToLp(parseUnits(withdrawAmount || '0', decimals))} LP`
    : null;

  if (!isConnected) {
    return (
      <Card className="bg-card border-border">
        <CardContent className="pt-6">
          <div className="text-center py-8">
            <AlertCircle className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">Connect your wallet to deposit or withdraw</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card border-border" data-testid="vault-actions">
      <CardHeader>
        <CardTitle className="text-lg">Vault Actions</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="deposit" className="gap-2" data-testid="deposit-tab">
              <ArrowDown className="w-4 h-4" />
              Deposit
            </TabsTrigger>
            <TabsTrigger value="withdraw" className="gap-2" data-testid="withdraw-tab">
              <ArrowUp className="w-4 h-4" />
              Withdraw
            </TabsTrigger>
          </TabsList>

          <TabsContent value="deposit" className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">LP Balance</span>
                <button 
                  onClick={setMaxDeposit}
                  className="text-primary hover:underline font-mono"
                  data-testid="max-deposit-btn"
                >
                  {parseFloat(formattedLpBalance).toFixed(6)} LP
                </button>
              </div>
              <Input
                type="number"
                placeholder="0.0"
                value={depositAmount}
                onChange={(e) => setDepositAmount(e.target.value)}
                className="font-mono text-lg h-12"
                data-testid="deposit-amount-input"
              />
            </div>

            {needsApproval() ? (
              <Button
                onClick={handleApprove}
                disabled={isApproving || isApproveConfirming}
                className="w-full h-12 glow-primary"
                data-testid="approve-btn"
              >
                {(isApproving || isApproveConfirming) ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Approving...
                  </>
                ) : (
                  'Approve LP Token'
                )}
              </Button>
            ) : (
              <Button
                onClick={handleDeposit}
                disabled={!depositAmount || isDepositing || isDepositConfirming}
                className="w-full h-12 glow-primary"
                data-testid="deposit-btn"
              >
                {(isDepositing || isDepositConfirming) ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Depositing...
                  </>
                ) : (
                  <>
                    <ArrowDown className="w-4 h-4 mr-2" />
                    Deposit
                  </>
                )}
              </Button>
            )}
          </TabsContent>

          <TabsContent value="withdraw" className="space-y-4">
            <div>
              <div className="flex justify-between items-center text-sm mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">
                    {withdrawMode === 'shares' ? 'Vault Shares' : 'LP Amount'}
                  </span>
                  <button
                    onClick={toggleWithdrawMode}
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                    data-testid="toggle-withdraw-mode"
                  >
                    <RotateCcw className="w-3 h-3" />
                    {withdrawMode === 'shares' ? 'Use LP' : 'Use Shares'}
                  </button>
                </div>
                <button 
                  onClick={setMaxWithdraw}
                  className="text-primary hover:underline font-mono"
                  data-testid="max-withdraw-btn"
                >
                  {withdrawMode === 'shares' 
                    ? `${parseFloat(formattedShareBalance).toFixed(6)} shares`
                    : `${parseFloat(formattedSharesAsLp).toFixed(6)} LP`
                  }
                </button>
              </div>
              <Input
                type="number"
                placeholder="0.0"
                value={withdrawAmount}
                onChange={(e) => setWithdrawAmount(e.target.value)}
                className="font-mono text-lg h-12"
                data-testid="withdraw-amount-input"
              />
              {withdrawPreview && withdrawAmount && (
                <p className="text-xs text-muted-foreground mt-1 font-mono">
                  {withdrawPreview}
                </p>
              )}
            </div>

            <Button
              onClick={handleWithdraw}
              disabled={!withdrawAmount || isWithdrawing || isWithdrawConfirming}
              variant="outline"
              className="w-full h-12 border-primary/50 hover:bg-primary/10"
              data-testid="withdraw-btn"
            >
              {(isWithdrawing || isWithdrawConfirming) ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Withdrawing...
                </>
              ) : (
                <>
                  <ArrowUp className="w-4 h-4 mr-2" />
                  Withdraw {withdrawMode === 'lp' ? 'LP' : 'Shares'}
                </>
              )}
            </Button>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
