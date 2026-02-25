"""
Test Beefy-style API endpoints for DeFi vault dashboard.
Tests: /api/prices, /api/lps, /api/tvl, /api/apy, /api/apy/{vault_id}
Also tests legacy endpoints: /api/vaults, /api/vaults/{id}/metrics
"""

import pytest
import requests
import os

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_VAULT_ID = "a304e705-c5cd-4ac5-aa0d-f35916a72e29"
ADMIN_PASSWORD = "vault_admin_2024"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestHealthEndpoint:
    """Health check tests - run first"""
    
    def test_health_check(self, api_client):
        """Test API health endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ Health check passed: {data}")


class TestBeefyPricesEndpoint:
    """Tests for /api/prices endpoint"""
    
    def test_prices_testnet_mock(self, api_client):
        """GET /api/prices?chain_id=84532 should return testnet mock prices"""
        response = api_client.get(f"{BASE_URL}/api/prices", params={"chain_id": 84532})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify testnet mock data structure
        assert "_meta" in data, "Missing _meta field"
        assert data["_meta"]["chain"] == 84532, "Wrong chain in meta"
        assert data["_meta"]["source"] == "testnet_mock", "Should indicate testnet_mock source"
        
        # Verify mock token price exists
        assert "0x0000000000000000000000000000000000000001" in data, "Missing mock token"
        assert data["0x0000000000000000000000000000000000000001"] == 100.0, "Mock price should be 100.0"
        print(f"✓ Testnet prices returned mock data: {data}")
    
    def test_prices_mainnet(self, api_client):
        """GET /api/prices?chain_id=8453 should return mainnet prices (cached)"""
        response = api_client.get(f"{BASE_URL}/api/prices", params={"chain_id": 8453})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify mainnet data structure
        assert "_meta" in data, "Missing _meta field"
        assert data["_meta"]["chain"] == 8453, "Wrong chain in meta"
        assert "count" in data["_meta"], "Missing count in meta"
        assert "updatedAt" in data["_meta"], "Missing updatedAt in meta"
        print(f"✓ Mainnet prices returned: {data}")
    
    def test_prices_default_chain(self, api_client):
        """GET /api/prices (no chain_id) should default to mainnet 8453"""
        response = api_client.get(f"{BASE_URL}/api/prices")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["_meta"]["chain"] == 8453, "Default should be mainnet"
        print("✓ Default chain is mainnet 8453")


class TestBeefyLpsEndpoint:
    """Tests for /api/lps endpoint"""
    
    def test_lps_testnet_mock(self, api_client):
        """GET /api/lps?chain_id=84532 should return testnet mock LP prices"""
        response = api_client.get(f"{BASE_URL}/api/lps", params={"chain_id": 84532})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify testnet mock data structure
        assert "_meta" in data, "Missing _meta field"
        assert data["_meta"]["chain"] == 84532, "Wrong chain in meta"
        assert data["_meta"]["source"] == "testnet_mock", "Should indicate testnet_mock source"
        
        # Verify mock LP price exists
        assert "0x0000000000000000000000000000000000000001" in data, "Missing mock LP"
        assert data["0x0000000000000000000000000000000000000001"] == 200.0, "Mock LP price should be 200.0"
        print(f"✓ Testnet LP prices returned mock data: {data}")
    
    def test_lps_mainnet(self, api_client):
        """GET /api/lps?chain_id=8453 should return mainnet LP prices (cached)"""
        response = api_client.get(f"{BASE_URL}/api/lps", params={"chain_id": 8453})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify mainnet data structure
        assert "_meta" in data, "Missing _meta field"
        assert data["_meta"]["chain"] == 8453, "Wrong chain in meta"
        assert "count" in data["_meta"], "Missing count in meta"
        assert "updatedAt" in data["_meta"], "Missing updatedAt in meta"
        print(f"✓ Mainnet LP prices returned: {data}")


class TestBeefyTvlEndpoint:
    """Tests for /api/tvl endpoint"""
    
    def test_tvl_returns_vault_data(self, api_client):
        """GET /api/tvl should return TVL per vault with dataQuality field"""
        response = api_client.get(f"{BASE_URL}/api/tvl")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify meta data
        assert "_meta" in data, "Missing _meta field"
        assert "totalVaults" in data["_meta"], "Missing totalVaults in meta"
        assert "updatedAt" in data["_meta"], "Missing updatedAt in meta"
        
        # If we have vaults, verify TVL structure
        vault_count = data["_meta"]["totalVaults"]
        print(f"✓ TVL endpoint returned {vault_count} vaults")
        
        # Check for test vault if it exists
        if TEST_VAULT_ID in data:
            vault_tvl = data[TEST_VAULT_ID]
            assert "tvl" in vault_tvl, "Missing tvl field"
            assert "chainId" in vault_tvl, "Missing chainId field"
            assert "dataQuality" in vault_tvl, "Missing dataQuality field"
            print(f"✓ Test vault TVL: {vault_tvl}")


class TestBeefyApyEndpoint:
    """Tests for /api/apy endpoint"""
    
    def test_apy_returns_breakdown(self, api_client):
        """GET /api/apy should return APY breakdown per vault"""
        response = api_client.get(f"{BASE_URL}/api/apy")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify meta data
        assert "_meta" in data, "Missing _meta field"
        assert "totalVaults" in data["_meta"], "Missing totalVaults in meta"
        assert "updatedAt" in data["_meta"], "Missing updatedAt in meta"
        
        vault_count = data["_meta"]["totalVaults"]
        print(f"✓ APY endpoint returned {vault_count} vaults")
        
        # Check for test vault APY breakdown structure
        if TEST_VAULT_ID in data:
            apy = data[TEST_VAULT_ID]
            required_fields = [
                "vaultApr", "vaultApy", "tradingApr", "totalApy",
                "compoundingsPerYear", "beefyPerformanceFee", "dataQuality"
            ]
            for field in required_fields:
                assert field in apy, f"Missing {field} in APY breakdown"
            print(f"✓ Test vault APY breakdown: {apy}")
    
    def test_apy_vault_specific(self, api_client):
        """GET /api/apy/{vault_id} should return APY breakdown for specific vault"""
        response = api_client.get(f"{BASE_URL}/api/apy/{TEST_VAULT_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify APY breakdown structure
        required_fields = [
            "vaultId", "vaultApr", "vaultApy", "tradingApr", "totalApy",
            "compoundingsPerYear", "beefyPerformanceFee", "dataQuality"
        ]
        for field in required_fields:
            assert field in data, f"Missing {field} in vault APY response"
        
        assert data["vaultId"] == TEST_VAULT_ID, "Vault ID mismatch"
        print(f"✓ Vault-specific APY: {data}")
    
    def test_apy_nonexistent_vault(self, api_client):
        """GET /api/apy/nonexistent should return error with dataQuality=error"""
        response = api_client.get(f"{BASE_URL}/api/apy/nonexistent")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should return error structure
        assert "error" in data or data.get("dataQuality") == "error", \
            "Expected error response for nonexistent vault"
        print(f"✓ Nonexistent vault returns error: {data}")


class TestLegacyVaultEndpoints:
    """Tests for legacy vault endpoints"""
    
    def test_get_vaults(self, api_client):
        """GET /api/vaults should return list of vaults"""
        response = api_client.get(f"{BASE_URL}/api/vaults")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Expected list of vaults"
        print(f"✓ Vaults list returned {len(data)} vaults")
        
        if len(data) > 0:
            vault = data[0]
            required_fields = ["id", "name", "chainId", "vaultAddress"]
            for field in required_fields:
                assert field in vault, f"Missing {field} in vault"
            print(f"✓ First vault: {vault.get('name')}")
    
    def test_get_vault_by_id(self, api_client):
        """GET /api/vaults/{id} should return specific vault"""
        response = api_client.get(f"{BASE_URL}/api/vaults/{TEST_VAULT_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data.get("id") == TEST_VAULT_ID, "Vault ID mismatch"
        assert "name" in data, "Missing name"
        assert "chainId" in data, "Missing chainId"
        print(f"✓ Vault by ID: {data.get('name')}")
    
    def test_get_vault_metrics(self, api_client):
        """GET /api/vaults/{id}/metrics should return vault metrics"""
        response = api_client.get(f"{BASE_URL}/api/vaults/{TEST_VAULT_ID}/metrics")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data.get("vaultId") == TEST_VAULT_ID, "Vault ID mismatch in metrics"
        
        # Check metric fields
        metric_fields = ["tvl", "apr", "apy", "pricePerShare", "dataQuality"]
        for field in metric_fields:
            assert field in data, f"Missing {field} in metrics"
        
        print(f"✓ Vault metrics: TVL={data.get('tvl')}, APY={data.get('apy')}%")


class TestAdminAuthentication:
    """Tests for admin authentication"""
    
    def test_admin_login(self, api_client):
        """Admin login should work with correct password"""
        response = api_client.post(f"{BASE_URL}/api/admin/login", 
                                   json={"password": ADMIN_PASSWORD})
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Login should succeed"
        print("✓ Admin login successful")
    
    def test_admin_login_wrong_password(self, api_client):
        """Admin login should fail with wrong password"""
        response = api_client.post(f"{BASE_URL}/api/admin/login",
                                   json={"password": "wrong_password"})
        assert response.status_code == 401, f"Should return 401: {response.text}"
        print("✓ Wrong password returns 401")
    
    def test_admin_check_authenticated(self, api_client):
        """Auth check after login should return authenticated=true"""
        # Login first
        login_response = api_client.post(f"{BASE_URL}/api/admin/login",
                                          json={"password": ADMIN_PASSWORD})
        assert login_response.status_code == 200
        
        # Check auth status
        check_response = api_client.get(f"{BASE_URL}/api/admin/check")
        assert check_response.status_code == 200
        data = check_response.json()
        assert data.get("authenticated") == True, "Should be authenticated after login"
        print("✓ Auth check returns authenticated=true")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
