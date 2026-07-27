import json


class TestCropInsurance:
    def test_deploy(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        assert c.next_id == u256(1)

    def test_empty_policy(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        r = c.get(u256(42))
        assert r == "none"

    def test_my_policies_empty(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        assert c.my_policies() == "empty"

    def test_claim_nonexistent(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        with direct_vm.expect_revert("not found"):
            c.claim(u256(999))

    def test_claim_not_owner(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        direct_vm.mock_web(r".*", {"status": 200, "body": "{}"})
        direct_vm.mock_llm(r".*", '{"payout_ratio": 0.0}')

        pid = c.add(u256(100))

        with direct_vm.prank("eve"):
            with direct_vm.expect_revert("not your policy"):
                c.claim(pid)

    def test_double_claim(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")
        direct_vm.mock_web(r".*", {"status": 200, "body": "{}"})
        direct_vm.mock_llm(r".*", '{"payout_ratio": 0.0}')

        pid = c.add(u256(100))
        c.claim(pid)
        with direct_vm.expect_revert("already claimed"):
            c.claim(pid)

    def test_claim_with_payout(self, direct_vm, direct_deploy):
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

        pid = c.add(u256(1000))
        c.claim(pid)
        r = c.get(pid)
        assert "clm=True" in r
        assert "paid=True" in r

    def test_owner_tracking(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")

        with direct_vm.prank("alice"):
            a1 = c.add(u256(100))
            a2 = c.add(u256(200))

        with direct_vm.prank("bob"):
            b1 = c.add(u256(300))

        with direct_vm.prank("alice"):
            mine = c.my_policies()
            parts = mine.split(",")
            assert str(int(a1)) in parts
            assert str(int(a2)) in parts

        with direct_vm.prank("bob"):
            assert c.my_policies() == str(int(b1))

    def test_seq_ids(self, direct_vm, direct_deploy):
        c = direct_deploy("crop_insurance.py")

        p1 = c.add(u256(100))
        p2 = c.add(u256(200))

        assert p1 == u256(1)
        assert p2 == u256(2)
        assert c.next_id == u256(3)
