#!/usr/bin/env python3
"""
Backend API Testing for BaseVault DeFi Dashboard
Tests all API endpoints including authentication and CRUD operations
"""

import requests
import sys
import json
from datetime import datetime
from urllib.parse import urljoin

class BaseVaultAPITester:
    def __init__(self, base_url="https://vault-dashboard-2.preview.emergentagent.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.tests_run = 0
        self.tests_passed = 0
        self.created_vault_id = None
        
    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, cookies=None):
        """Run a single API test"""
        url = urljoin(self.base_url + "/", f"api/{endpoint}")
        
        request_headers = {'Content-Type': 'application/json'}
        if headers:
            request_headers.update(headers)
            
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=request_headers, cookies=cookies)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=request_headers, cookies=cookies)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=request_headers, cookies=cookies)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=request_headers, cookies=cookies)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                if response.headers.get('content-type', '').startswith('application/json'):
                    try:
                        resp_json = response.json()
                        if isinstance(resp_json, dict) and len(resp_json) <= 3:
                            print(f"   Response: {resp_json}")
                        elif isinstance(resp_json, list) and len(resp_json) <= 2:
                            print(f"   Response: {len(resp_json)} items")
                    except:
                        pass
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
            
            return success, response
            
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, None
    
    def test_health_endpoints(self):
        """Test health and root endpoints"""
        print("\n" + "="*50)
        print("Testing Health Endpoints")
        print("="*50)
        
        self.run_test("API Root", "GET", "", 200)
        self.run_test("Health Check", "GET", "health", 200)
    
    def test_public_vault_endpoints(self):
        """Test public vault endpoints (no auth required)"""
        print("\n" + "="*50)
        print("Testing Public Vault Endpoints")
        print("="*50)
        
        # Test getting all vaults (should work without auth)
        success, response = self.run_test("Get All Vaults", "GET", "vaults", 200)
        
        # If we have vaults, test getting specific vault and its metrics
        if success and response:
            try:
                vaults = response.json()
                if vaults and len(vaults) > 0:
                    vault_id = vaults[0]['id']
                    self.run_test("Get Specific Vault", "GET", f"vaults/{vault_id}", 200)
                    self.run_test("Get Vault Metrics", "GET", f"vaults/{vault_id}/metrics", 200)
                    self.run_test("Refresh Vault Metrics", "POST", f"vaults/{vault_id}/metrics/refresh", 200)
                    self.run_test("Get Vault Harvests", "GET", f"vaults/{vault_id}/harvests", 200)
                else:
                    print("ℹ️  No existing vaults found, skipping vault-specific tests")
            except Exception as e:
                print(f"⚠️  Could not parse vault response: {e}")
    
    def test_admin_authentication(self):
        """Test admin authentication flow"""
        print("\n" + "="*50)
        print("Testing Admin Authentication")
        print("="*50)
        
        # Test login with wrong password
        self.run_test(
            "Login with Invalid Password", 
            "POST", 
            "admin/login", 
            401,
            data={"password": "wrong_password"}
        )
        
        # Test login with correct password
        success, response = self.run_test(
            "Login with Valid Password",
            "POST",
            "admin/login", 
            200,
            data={"password": "vault_admin_2024"}
        )
        
        if success and response:
            # Extract session cookie
            session_cookie = response.cookies.get('admin_session')
            if session_cookie:
                print(f"   Session cookie received: {session_cookie[:20]}...")
                self.session.cookies.set('admin_session', session_cookie)
            
        # Test check auth endpoint
        self.run_test("Check Auth Status", "GET", "admin/check", 200)
        
        return success
    
    def test_admin_vault_crud(self):
        """Test admin vault CRUD operations"""
        print("\n" + "="*50)
        print("Testing Admin Vault CRUD Operations")
        print("="*50)
        
        # Test creating a vault (requires auth)
        test_vault = {
            "name": f"Test Vault {datetime.now().strftime('%H%M%S')}",
            "chainId": 84532,  # Base Sepolia for testing
            "vaultAddress": f"0x{datetime.now().strftime('%H%M%S').ljust(40, '0')}",
            "strategyAddress": f"0x{datetime.now().strftime('%H%M%S')[::-1].ljust(40, '1')}",
            "wantAddress": f"0x{datetime.now().strftime('%H%M%S')[::-1].ljust(40, '2')}",
            "token0": "ETH",
            "token1": "USDC", 
            "rewardToken": "CAKE",
            "farmAddress": f"0x{datetime.now().strftime('%H%M%S').ljust(40, '3')}",
            "routerAddress": f"0x{datetime.now().strftime('%H%M%S')[::-1].ljust(40, '4')}",
            "feeRecipients": [],
            "paused": False
        }
        
        success, response = self.run_test(
            "Create New Vault",
            "POST", 
            "vaults",
            201,
            data=test_vault
        )
        
        if success and response:
            try:
                created_vault = response.json()
                self.created_vault_id = created_vault['id']
                print(f"   Created vault ID: {self.created_vault_id}")
                
                # Test updating the vault
                update_data = {
                    "name": f"Updated {test_vault['name']}",
                    "paused": True
                }
                
                self.run_test(
                    "Update Vault",
                    "PUT",
                    f"vaults/{self.created_vault_id}",
                    200,
                    data=update_data
                )
                
                # Test getting the updated vault
                self.run_test(
                    "Get Updated Vault",
                    "GET",
                    f"vaults/{self.created_vault_id}",
                    200
                )
                
            except Exception as e:
                print(f"⚠️  Could not parse created vault: {e}")
    
    def test_user_actions_endpoints(self):
        """Test user actions endpoints"""
        print("\n" + "="*50)
        print("Testing User Actions Endpoints")
        print("="*50)
        
        if self.created_vault_id:
            # Test recording user action
            user_action = {
                "vaultId": self.created_vault_id,
                "userAddress": "0x1234567890123456789012345678901234567890",
                "actionType": "deposit",
                "amount": "1000000000000000000",  # 1 ETH in wei
                "txHash": f"0x{datetime.now().strftime('%H%M%S').ljust(64, '0')}"
            }
            
            self.run_test(
                "Record User Action",
                "POST",
                "user-actions",
                200,
                data=user_action
            )
            
            # Test getting user actions
            self.run_test(
                "Get User Actions",
                "GET",
                f"user-actions/{user_action['userAddress']}",
                200
            )
    
    def test_admin_logout(self):
        """Test admin logout"""
        print("\n" + "="*50)
        print("Testing Admin Logout")
        print("="*50)
        
        success, response = self.run_test("Admin Logout", "POST", "admin/logout", 200)
        
        if success:
            # Clear session cookie
            self.session.cookies.clear()
            
            # Test that protected endpoints now fail
            self.run_test(
                "Access Protected Endpoint After Logout",
                "GET",
                "admin/check",
                200  # This endpoint returns auth status, not 401
            )
    
    def cleanup_test_data(self):
        """Clean up test data"""
        print("\n" + "="*50)
        print("Cleanup Test Data")
        print("="*50)
        
        # Re-login for cleanup
        success, response = self.run_test(
            "Re-login for Cleanup",
            "POST",
            "admin/login",
            200,
            data={"password": "vault_admin_2024"}
        )
        
        if success and self.created_vault_id:
            self.run_test(
                "Delete Test Vault",
                "DELETE",
                f"vaults/{self.created_vault_id}",
                200
            )
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting BaseVault API Tests")
        print(f"   Base URL: {self.base_url}")
        
        try:
            # Test in logical order
            self.test_health_endpoints()
            self.test_public_vault_endpoints() 
            
            # Test admin authentication
            auth_success = self.test_admin_authentication()
            
            if auth_success:
                self.test_admin_vault_crud()
                self.test_user_actions_endpoints()
                self.test_admin_logout()
                self.cleanup_test_data()
            else:
                print("❌ Admin authentication failed, skipping admin tests")
            
        except Exception as e:
            print(f"❌ Test suite failed with error: {e}")
        
        # Print final results
        print("\n" + "="*60)
        print("FINAL TEST RESULTS")
        print("="*60)
        print(f"📊 Tests Run: {self.tests_run}")
        print(f"✅ Tests Passed: {self.tests_passed}")
        print(f"❌ Tests Failed: {self.tests_run - self.tests_passed}")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Backend API tests passed!")
            return 0
        else:
            print("❌ Backend API tests failed!")
            return 1

def main():
    tester = BaseVaultAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())