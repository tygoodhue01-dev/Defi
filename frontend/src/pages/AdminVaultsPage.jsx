import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Plus,
  Edit,
  Trash2,
  Loader2,
  LogOut,
  Vault,
  AlertCircle,
  Check,
  X,
  Pause,
  Play,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ScrollArea } from '@/components/ui/scroll-area';
import { authApi, vaultApi } from '@/lib/api';
import { formatAddress, formatDateTime } from '@/lib/utils';

const emptyVault = {
  name: '',
  chainId: 84532, // Default to Base Sepolia for testing
  vaultAddress: '',
  strategyAddress: '',
  wantAddress: '',
  token0: '',
  token1: '',
  rewardToken: '',
  farmAddress: '',
  routerAddress: '',
  feeRecipients: [],
  paused: false,
  experimental: false,
};

export default function AdminVaultsPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [vaults, setVaults] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingVault, setEditingVault] = useState(null);
  const [vaultToDelete, setVaultToDelete] = useState(null);
  const [formData, setFormData] = useState(emptyVault);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Check authentication
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const { authenticated } = await authApi.checkAuth();
        if (!authenticated) {
          navigate('/admin/login');
          return;
        }
        setAuthenticated(true);
        fetchVaults();
      } catch (error) {
        navigate('/admin/login');
      }
    };
    checkAuth();
  }, [navigate]);

  const fetchVaults = async () => {
    try {
      setLoading(true);
      const data = await vaultApi.getVaults();
      setVaults(data);
    } catch (error) {
      console.error('Failed to fetch vaults:', error);
      toast.error('Failed to load vaults');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
      toast.success('Logged out');
      navigate('/admin/login');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const openCreateDialog = () => {
    setEditingVault(null);
    setFormData(emptyVault);
    setDialogOpen(true);
  };

  const openEditDialog = (vault) => {
    setEditingVault(vault);
    setFormData({
      ...vault,
      feeRecipients: vault.feeRecipients || [],
      experimental: vault.experimental || false,
    });
    setDialogOpen(true);
  };

  const openDeleteDialog = (vault) => {
    setVaultToDelete(vault);
    setDeleteDialogOpen(true);
  };

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      
      // Validate required fields
      const requiredFields = ['name', 'vaultAddress', 'strategyAddress', 'wantAddress', 'token0', 'token1'];
      for (const field of requiredFields) {
        if (!formData[field]?.trim()) {
          toast.error(`${field} is required`);
          return;
        }
      }

      if (editingVault) {
        await vaultApi.updateVault(editingVault.id, formData);
        toast.success('Vault updated successfully');
      } else {
        await vaultApi.createVault(formData);
        toast.success('Vault created successfully');
      }
      
      setDialogOpen(false);
      fetchVaults();
    } catch (error) {
      console.error('Save failed:', error);
      toast.error('Failed to save vault');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!vaultToDelete) return;
    
    try {
      setDeleting(true);
      await vaultApi.deleteVault(vaultToDelete.id);
      toast.success('Vault deleted successfully');
      setDeleteDialogOpen(false);
      setVaultToDelete(null);
      fetchVaults();
    } catch (error) {
      console.error('Delete failed:', error);
      toast.error('Failed to delete vault');
    } finally {
      setDeleting(false);
    }
  };

  if (!authenticated) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 py-8 md:py-12" data-testid="admin-vaults-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold">Admin Panel</h1>
          <p className="text-muted-foreground">Manage vault configurations</p>
        </div>
        <div className="flex gap-3">
          <Button onClick={openCreateDialog} className="gap-2" data-testid="create-vault-btn">
            <Plus className="w-4 h-4" />
            Create Vault
          </Button>
          <Button variant="outline" onClick={handleLogout} className="gap-2" data-testid="logout-btn">
            <LogOut className="w-4 h-4" />
            Logout
          </Button>
        </div>
      </div>

      {/* Vaults Table */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Vault className="w-5 h-5" />
            Vaults ({vaults.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          ) : vaults.length === 0 ? (
            <div className="text-center py-12">
              <AlertCircle className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground mb-4">No vaults configured yet</p>
              <Button onClick={openCreateDialog} className="gap-2">
                <Plus className="w-4 h-4" />
                Create First Vault
              </Button>
            </div>
          ) : (
            <ScrollArea className="w-full">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Chain</TableHead>
                    <TableHead>Tokens</TableHead>
                    <TableHead>Vault Address</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {vaults.map((vault) => (
                    <TableRow key={vault.id} data-testid={`vault-row-${vault.id}`}>
                      <TableCell className="font-medium">{vault.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {vault.chainId === 8453 ? 'Base' : 'Sepolia'}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {vault.token0}/{vault.token1}
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {formatAddress(vault.vaultAddress)}
                      </TableCell>
                      <TableCell>
                        {vault.paused ? (
                          <Badge variant="destructive" className="gap-1">
                            <Pause className="w-3 h-3" />
                            Paused
                          </Badge>
                        ) : (
                          <Badge className="bg-green-500/20 text-green-400 border-green-500/30 gap-1">
                            <Play className="w-3 h-3" />
                            Active
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDateTime(vault.createdAt)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openEditDialog(vault)}
                            data-testid={`edit-vault-${vault.id}`}
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openDeleteDialog(vault)}
                            className="text-destructive hover:text-destructive"
                            data-testid={`delete-vault-${vault.id}`}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto bg-card">
          <DialogHeader>
            <DialogTitle>
              {editingVault ? 'Edit Vault' : 'Create New Vault'}
            </DialogTitle>
            <DialogDescription>
              {editingVault
                ? 'Update the vault configuration below.'
                : 'Fill in the vault details to create a new vault.'}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Vault Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  placeholder="ETH-USDC LP Vault"
                  data-testid="vault-name-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="chainId">Chain *</Label>
                <Select
                  value={formData.chainId.toString()}
                  onValueChange={(v) => handleInputChange('chainId', parseInt(v))}
                >
                  <SelectTrigger data-testid="chain-select">
                    <SelectValue placeholder="Select chain" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="8453">Base Mainnet</SelectItem>
                    <SelectItem value="84532">Base Sepolia</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="vaultAddress">Vault Address *</Label>
              <Input
                id="vaultAddress"
                value={formData.vaultAddress}
                onChange={(e) => handleInputChange('vaultAddress', e.target.value)}
                placeholder="0x..."
                className="font-mono"
                data-testid="vault-address-input"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="strategyAddress">Strategy Address *</Label>
              <Input
                id="strategyAddress"
                value={formData.strategyAddress}
                onChange={(e) => handleInputChange('strategyAddress', e.target.value)}
                placeholder="0x..."
                className="font-mono"
                data-testid="strategy-address-input"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="wantAddress">Want Token (LP) Address *</Label>
              <Input
                id="wantAddress"
                value={formData.wantAddress}
                onChange={(e) => handleInputChange('wantAddress', e.target.value)}
                placeholder="0x..."
                className="font-mono"
                data-testid="want-address-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="token0">Token 0 *</Label>
                <Input
                  id="token0"
                  value={formData.token0}
                  onChange={(e) => handleInputChange('token0', e.target.value)}
                  placeholder="ETH"
                  data-testid="token0-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="token1">Token 1 *</Label>
                <Input
                  id="token1"
                  value={formData.token1}
                  onChange={(e) => handleInputChange('token1', e.target.value)}
                  placeholder="USDC"
                  data-testid="token1-input"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="rewardToken">Reward Token</Label>
              <Input
                id="rewardToken"
                value={formData.rewardToken}
                onChange={(e) => handleInputChange('rewardToken', e.target.value)}
                placeholder="CAKE"
                data-testid="reward-token-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="farmAddress">Farm Address</Label>
                <Input
                  id="farmAddress"
                  value={formData.farmAddress}
                  onChange={(e) => handleInputChange('farmAddress', e.target.value)}
                  placeholder="0x..."
                  className="font-mono"
                  data-testid="farm-address-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="routerAddress">Router Address</Label>
                <Input
                  id="routerAddress"
                  value={formData.routerAddress}
                  onChange={(e) => handleInputChange('routerAddress', e.target.value)}
                  placeholder="0x..."
                  className="font-mono"
                  data-testid="router-address-input"
                />
              </div>
            </div>

            <div className="flex items-center justify-between p-4 rounded-lg bg-muted/30">
              <div>
                <Label htmlFor="paused" className="text-base">Paused</Label>
                <p className="text-sm text-muted-foreground">
                  Pause deposits and withdrawals
                </p>
              </div>
              <Switch
                id="paused"
                checked={formData.paused}
                onCheckedChange={(checked) => handleInputChange('paused', checked)}
                data-testid="paused-switch"
              />
            </div>

            <div className="flex items-center justify-between p-4 rounded-lg bg-yellow-500/5 border border-yellow-500/20">
              <div>
                <Label htmlFor="experimental" className="text-base">Experimental (Beta)</Label>
                <p className="text-sm text-muted-foreground">
                  Mark as experimental/beta vault
                </p>
              </div>
              <Switch
                id="experimental"
                checked={formData.experimental}
                onCheckedChange={(checked) => handleInputChange('experimental', checked)}
                data-testid="experimental-switch"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving} data-testid="save-vault-btn">
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  {editingVault ? 'Update' : 'Create'}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="bg-card">
          <DialogHeader>
            <DialogTitle>Delete Vault</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{vaultToDelete?.name}"? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
              data-testid="confirm-delete-btn"
            >
              {deleting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
