import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// Format address to show first 6 and last 4 characters
export function formatAddress(address) {
  if (!address) return '';
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

// Format large numbers with commas
export function formatNumber(num, decimals = 2) {
  if (!num) return '0';
  const n = parseFloat(num);
  if (isNaN(n)) return '0';
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// Format USD values
export function formatUSD(value) {
  if (!value) return '$0.00';
  const n = parseFloat(value);
  if (isNaN(n)) return '$0.00';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

// Format percentage
export function formatPercent(value) {
  if (!value) return '0%';
  const n = parseFloat(value);
  if (isNaN(n)) return '0%';
  return `${n.toFixed(2)}%`;
}

// Format timestamp to relative time
export function formatTimeAgo(timestamp) {
  if (!timestamp) return 'Never';
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now - date;
  
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (minutes > 0) return `${minutes}m ago`;
  return 'Just now';
}

// Format datetime
export function formatDateTime(timestamp) {
  if (!timestamp) return '-';
  return new Date(timestamp).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Parse wei to human readable
export function formatFromWei(value, decimals = 18, displayDecimals = 4) {
  if (!value) return '0';
  const n = BigInt(value);
  const divisor = BigInt(10 ** decimals);
  const whole = n / divisor;
  const fraction = n % divisor;
  const fractionStr = fraction.toString().padStart(decimals, '0').slice(0, displayDecimals);
  return `${whole}.${fractionStr}`;
}

// Convert human readable to wei
export function toWei(value, decimals = 18) {
  if (!value) return '0';
  const [whole, fraction = ''] = value.split('.');
  const paddedFraction = fraction.padEnd(decimals, '0').slice(0, decimals);
  return BigInt(whole + paddedFraction).toString();
}
