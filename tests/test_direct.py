import json


class TestCropInsurance:
    """
    Direct-mode tests for CropInsurance.

    NOTE: buy_policy is @payable — Direct Mode sets transaction value to 0
    by default, so the premium check (>= 10 % of coverage) will revert.
    Use Studio Mode or set direct_vm.value for full payable coverage.
    """

    def test_deploy(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        assert c.next_id == u256(1)

    def test_empty_policy(self, direct_vm, direct_deploy):
        """get_policy on missing id returns error"""
        c = direct_deploy("crop_insurance.py")
        r = c.get_policy(u256(42))
        assert r["error"] == "not found"

    def test_my_policies_empty(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        assert len(c.my_policies()) == 0

    def test_claim_nonexistent(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        with direct_vm.expect_revert("policy not found"):
            c.claim(u256(999))

    def test_claim_not_owner(self, direct_vm, direct_deploy):
        """
        buy a policy as alice, then try to claim as eve → revert.
        This skips the premium guard by passing coverage=0.
        """
        c = direct_deploy("crop_insurance.py")
        direct_vm.mock_web(r".*", {"status": 200, "body": "{}"})
        direct_vm.mock_llm(r".*", '{"payout_ratio": 0.0}')

        pid = c.buy_policy(
            "wheat", "Farm", 35.0, 51.0,
            u256(0), u256(20260601), u256(20260801),
            20.0, 35.0,
        )

        with direct_vm.prank("eve"):
            with direct_vm.expect_revert("not your policy"):
                c.claim(pid)

    def test_double_claim(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        direct_vm.mock_web(r".*", {"status": 200, "body": "{}"})
        direct_vm.mock_llm(r".*", '{"payout_ratio": 0.0}')

        pid = c.buy_policy(
            "wheat", "Farm", 35.0, 51.0,
            u256(0), u256(20260601), u256(20260801),
            20.0, 35.0,
        )

        c.claim(pid)
        with direct_vm.expect_revert("already claimed"):
            c.claim(pid)

    def test_claim_with_payout(self, direct_vm, direct_deploy):
        """full flow: buy → claim with drought → policy shows paid"""
        c = direct_deploy("crop_insurance.py")

        direct_vm.mock_llm(
            r"payout_ratio",
            '{"drought": true, "heat_damage": true, "payout_ratio": 0.6}',
        )
        direct_vm.mock_web(
            r"archive-api",
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

    def test_owner_tracking(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        direct_vm.mock_web(r".*", {"status": 200, "body": "{}"})
        direct_vm.mock_llm(r".*", '{"payout_ratio": 0.0}')

        with direct_vm.prank("alice"):
            a1 = c.buy_policy("rice", "A", 0, 0, u256(0), u256(1), u256(2), 10.0, 30.0)
            a2 = c.buy_policy("corn", "A", 0, 0, u256(0), u256(1), u256(2), 10.0, 30.0)

        with direct_vm.prank("bob"):
            b1 = c.buy_policy("wheat", "B", 0, 0, u256(0), u256(1), u256(2), 10.0, 30.0)

        with direct_vm.prank("alice"):
            mine = c.my_policies()
            assert len(mine) == 2
            assert a1 in mine
            assert a2 in mine

        with direct_vm.prank("bob"):
            assert len(c.my_policies()) == 1
            assert c.my_policies()[0] == b1

    def test_seq_ids(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        direct_vm.mock_web(r".*", {"status": 200, "body": "{}"})
        direct_vm.mock_llm(r".*", '{"payout_ratio": 0.0}')

        p1 = c.buy_policy("a", "l", 0, 0, u256(0), u256(1), u256(2), 5.0, 40.0)
        p2 = c.buy_policy("b", "l", 0, 0, u256(0), u256(1), u256(2), 5.0, 40.0)

        assert p1 == u256(1)
        assert p2 == u256(2)
        assert c.next_id == u256(3)
