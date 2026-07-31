"""Deploy CropInsurance to GenLayer Bradbury testnet"""
import json
import os
import sys
from genlayer_py import create_account, create_client, testnet_bradbury
from genlayer_py.contracts.actions import deploy_contract

def main():
    key = os.environ.get("GENLAYER_PRIVATE_KEY")
    if not key:
        print("ERROR: Set GENLAYER_PRIVATE_KEY environment variable first")
        print("  PowerShell: $env:GENLAYER_PRIVATE_KEY = 'your_key_here'")
        sys.exit(1)

    account = create_account(private_key=key)
    client = create_client(rpc=testnet_bradbury.rpc_urls["default"]["http"][0])

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "crop_insurance.py")) as f:
        source = f.read()

    print(f"Chain: Bradbury (id={testnet_bradbury.id})")
    print(f"Account: {account.address}")
    print("Deploying CropInsurance...")

    result = deploy_contract(client, code=source, account=account, args=[])
    addr = str(result).lower()
    print(f"  Result: {result}")

    if addr.startswith("0x") and len(addr) == 42:
        print(f"  Contract address: {addr}")
        info = {"name": "CropInsurance", "address": addr, "chain_id": testnet_bradbury.id, "tx_hash": result}
        with open(os.path.join(here, "deploy_crop_insurance.json"), "w") as f:
            json.dump(info, f, indent=2)
        print("  Saved: deploy_crop_insurance.json")
    else:
        print("  WARNING: unexpected return format - check explorer for address")

if __name__ == "__main__":
    main()
