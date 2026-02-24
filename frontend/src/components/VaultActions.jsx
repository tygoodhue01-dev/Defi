import React, { useState, useEffect } from 'react';
import { useAccount, useReadContract, useWriteContract, useWaitForTransactionReceipt } from 'wagmi';
import { parseUnits, formatUnits } from 'viem';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Loader2, ArrowDown, ArrowUp, Check, AlertCircle } from 'lucide-react';
import { ERC20_ABI, VAULT_ABI } from '@/lib/contracts';
import { formatFromWei, formatNumber } from '@/lib/utils';
import { userActionApi } from '@/lib/api';

export function VaultActions({ vault, onActionComplete }) {
  const { address, isConnected } = useAccount();
  const [depositAmount, setDepositAmount] = useState('');
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [activeTab, setActiveTab] = useState('deposit');

  const vaultAddress = vault.vaultAddress;
  const wantAddress = vault.wantAddress;

  // Read LP token balance
  const { data: lpBalance, refetch: refetchLpBalance } = useReadContract({
    address: wantAddress,
    abi: ERC20_ABI,
    functionName: 'balanceOf',
    args: [address],
    query: { enabled: !!address && isConnected },
  });

  // Read vault share balance
  const { data: shareBalance, refetch: refetchShareBalance } = useReadContract({
    address: vaultAddress,
    abi: VAULT_ABI,
    functionName: 'balanceOf',
    args: [address],
    query: { enabled: !!address && isConnected },
  });

  // Read allowance
  const { data: allowance, refetch: refetchAllowance } = useReadContract({
    address: wantAddress,
    abi: ERC20_ABI,
    functionName: 'allowance',
    args: [address, vaultAddress],
    query: { enabled: !!address && isConnected },
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
      setDepositAmount('');
      
      // Record user action
      userActionApi.recordAction({
        vaultId: vault.id,
        userAddress: address.toLowerCase(),
        actionType: 'deposit',
        amount: parseUnits(depositAmount || '0', 18).toString(),
        txHash: depositHash,
      }).catch(console.error);
      
      onActionComplete?.();
    }
  }, [isDepositSuccess, depositHash]);

  // Handle withdraw success
  useEffect(() => {
    if (isWithdrawSuccess && withdrawHash) {
      toast.success('Withdrawal successful!');
      refetchLpBalance();
      refetchShareBalance();
      setWithdrawAmount('');
      
      // Record user action
      userActionApi.recordAction({
        vaultId: vault.id,
        userAddress: address.toLowerCase(),
        actionType: 'withdraw',
        amount: parseUnits(withdrawAmount || '0', 18).toString(),
        txHash: withdrawHash,
      }).catch(console.error);
      
      onActionComplete?.();
    }
  }, [isWithdrawSuccess, withdrawHash]);

  const needsApproval = () => {
    if (!depositAmount || !allowance) return false;
    try {
      const amount = parseUnits(depositAmount, 18);
      return allowance < amount;
    } catch {
      return false;
    }
  };

  const handleApprove = () => {
    if (!depositAmount) return;
    try {
      const amount = parseUnits(depositAmount, 18);
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
      const amount = parseUnits(depositAmount, 18);
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
      const amount = parseUnits(withdrawAmount, 18);
      withdraw({
        address: vaultAddress,
        abi: VAULT_ABI,
        functionName: 'withdraw',
        args: [amount],
      });
    } catch (error) {
      toast.error('Invalid amount');
    }
  };

  const setMaxDeposit = () => {
    if (lpBalance) {
      setDepositAmount(formatUnits(lpBalance, 18));
    }
  };

  const setMaxWithdraw = () => {
    if (shareBalance) {
      setWithdrawAmount(formatUnits(shareBalance, 18));
    }
  };

  const formattedLpBalance = lpBalance ? formatFromWei(lpBalance.toString()) : '0';
  const formattedShareBalance = shareBalance ? formatFromWei(shareBalance.toString()) : '0';

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
                  {formattedLpBalance} LP
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
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">Vault Shares</span>
                <button 
                  onClick={setMaxWithdraw}
                  className="text-primary hover:underline font-mono"
                  data-testid="max-withdraw-btn"
                >
                  {formattedShareBalance} shares
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
                  Withdraw
                </>
              )}
            </Button>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
