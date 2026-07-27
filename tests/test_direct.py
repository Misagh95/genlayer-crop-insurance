import json


class TestCropInsurance:
    """Direct-mode tests for CropInsurance contract.

    NOTE: buy_policy is @payable — in Direct Mode the transaction value
    defaults to 0, so the premium check (>= 10 % of coverage) will fail.
    Full payable testing requires Studio Mode or a localnet.
    These tests focus on state logic, view methods, and the claim flow
    using mock web/LLM responses.
    """

    def test_deploy(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        assert c.next_id == u256(1)

    def test_empty_view(self, direct_vm, direct_deploy):
        """get_policy on non-existent id returns error dict"""
        c = direct_deploy("crop_insurance.py")
        result = c.get_policy(u256(42))
        assert result["error"] == "not found"

    def test_my_policies_empty(self, direct_vm, direct_deploy):
        """my_policies returns empty list for fresh caller"""
        c = direct_deploy("crop_insurance.py")
        mine = c.my_policies()
        assert len(mine) == 0

    def test_claim_nonexistent(self, direct_vm, direct_deploy):
        """claiming a policy that doesn't exist reverts"""
        c = direct_deploy("crop_insurance.py")
        with direct_vm.expect_revert("policy not found"):
            c.claim(u256(999))

    def test_claim_not_owner(self, direct_vm, direct_deploy):
        """caller who didn't buy the policy cannot claim it"""
        c = direct_deploy("crop_insurance.py")

        # mock — these are needed when the contract does write()
        direct_vm.mock_web(r".*", {"status": 200, "body": "{}"})
        direct_vm.mock_llm(r".*", '{"payout_ratio": 0.0}')

        pid = c.buy_policy(
            "wheat", "Farm", 35.0, 51.0,
            u256(1000), u256(20260601), u256(20260801),
            20.0, 35.0,
        )

        with direct_vm.prank("eve"):
            with direct_vm.expect_revert("not your policy"):
                c.claim(pid)

    def test_double_claim_reverts(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        direct_vm.mock_web(r".*", {"status": 200, "body": "{}"})
        direct_vm.mock_llm(r".*", '{"payout_ratio": 0.0}')

        pid = c.buy_policy(
            "wheat", "Farm", 35.0, 51.0,
            u256(1000), u256(20260601), u256(20260801),
            20.0, 35.0,
        )

        c.claim(pid)  # first claim works (payout=0 since no real damage)
        with direct_vm.expect_revert("already claimed"):
            c.claim(pid)  # second fails

    def test_claim_with_payout(self, direct_vm, direct_deploy):
        """full flow: buy → claim with drought → policy shows paid"""
        c = direct_deploy("crop_insurance.py")

        # mock LLM: return a 60 % payout ratio
        direct_vm.mock_llm(
            r"payout_ratio",
            '{"drought": true, "heat_damage": true, "payout_ratio": 0.6}',
        )
        # mock weather API
        direct_vm.mock_web(
            r            r"archive-api",
            {
                "status": 200,
                "body": json.dumps({
                    "daily": {
                        "precipitation_sum": [0.0, 0.0],
                        "temperature_2m_max": [44.0, 42.0],
                    }
                }),
            },
        )

        pid = c.buy_policy(
            "wheat", "Hot Farm", 35.0, 51.0,
            u256(1000), u256(20260601), u256(20260801),
            20.0, 35.0,
        )

        c.claim(pid)
        p = c.get_policy(pid)
        assert p["claimed"] is True
        assert p["paid"] is True
        # coverage was 1000, ratio 0.6 → would transfer 600

    def test_owner_tracking(self, direct_vm, direct_deploy):
        """buy from two users, verify my_policies is per-user"""
        c = direct_deploy("crop_insurance.py")
        direct_vm.mock_web(r".*", {"status": 200, "body": "{}"})
        direct_vm.mock_llm(r".*", '{"payout_ratio": 0.0}')

        with direct_vm.prank("alice"):
            a1 = c.buy_policy("rice", "A-land", 0, 0, u256(500), u256(1), u256(2), 10.0, 30.0)
            a2 = c.buy_policy("corn", "A-land", 0, 0, u256(500), u256(1), u256(2), 10.0, 30.0)

        with direct_vm.prank("bob"):
            b1 = c.buy_policy("wheat", "B-land", 0, 0, u256(500), u256(1), u256(2), 10.0, 30.0)

        with direct_vm.prank("alice"):
            alice_policies = c.my_policies()
            assert len(alice_policies) == 2
            assert a1 in alice_policies
            assert a2 in alice_policies

        with direct_vm.prank("bob"):
            bob_policies = c.my_policies()
            assert len(bob_policies) == 1
            assert bob_policies[0] == b1

    def test_concurrent_policies(self, direct_vm, direct_deploy):
        """multiple policies on same contract, sequential ids"""
        c = direct_deploy("crop_insurance.py")
        direct_vm.mock_web(r".*", {"status": 200, "body": "{}"})
        direct_vm.mock_llm(r".*", '{"payout_ratio": 0.0}')

        p1 = c.buy_policy("a", "loc", 0, 0, u256(100), u256(1), u256(2), 5.0, 40.0)
        p2 = c.buy_policy("b", "loc", 0, 0, u256(200), u256(1), u256(2), 5.0, 40.0)
        p3 = c.buy_policy("c", "loc", 0, 0, u256(300), u256(1), u256(2), 5.0, 40.0)

        assert p1 == u256(1)
        assert p2 == u256(2)
        assert p3 == u256(3)
        assert c.next_id == u256(4)
