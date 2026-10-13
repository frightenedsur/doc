import argparse
import os
import sys

import requests

BUNDLE_STATUS_BATCH_SIZE = 5


def parse_args():
    parser = argparse.ArgumentParser(description="check land status for jito bundle ids")
    parser.add_argument("bundle_ids", nargs="*", help="bundle uuids to check")
    parser.add_argument("-f", "--bundle-ids-file", help="file with one bundle uuid per line")
    parser.add_argument(
        "--block-engine-url",
        default=os.environ.get("JITO_BLOCK_ENGINE_URL", "https://mainnet.block-engine.jito.wtf"),
    )
    return parser.parse_args()


def load_bundle_ids_from_file(bundle_ids_file):
    with open(bundle_ids_file, "r") as f:
        return [line.strip() for line in f if line.strip()]


def chunk_bundle_ids(bundle_ids, batch_size):
    for start_index in range(0, len(bundle_ids), batch_size):
        yield bundle_ids[start_index:start_index + batch_size]


def fetch_bundle_statuses(block_engine_url, bundle_id_batch):
    rpc_endpoint = f"{block_engine_url.rstrip('/')}/api/v1/bundles"
    request_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBundleStatuses",
        "params": [bundle_id_batch],
    }
    response = requests.post(rpc_endpoint, json=request_payload, timeout=10)
    response.raise_for_status()
    response_body = response.json()
    if "error" in response_body:
        raise RuntimeError(f"getBundleStatuses error: {response_body['error']}")
    return response_body["result"]["value"]


def is_bundle_landed(bundle_status_entry):
    if bundle_status_entry is None:
        return False
    return bundle_status_entry.get("confirmation_status") in ("confirmed", "finalized")


def main():
    args = parse_args()

    all_bundle_ids = list(args.bundle_ids)
    if args.bundle_ids_file:
        all_bundle_ids.extend(load_bundle_ids_from_file(args.bundle_ids_file))

    if not all_bundle_ids:
        print("no bundle ids given, pass them as args or with -f", file=sys.stderr)
        sys.exit(1)

    bundle_status_by_id = {}
    for bundle_id_batch in chunk_bundle_ids(all_bundle_ids, BUNDLE_STATUS_BATCH_SIZE):
        for requested_bundle_id, bundle_status_entry in zip(
            bundle_id_batch, fetch_bundle_statuses(args.block_engine_url, bundle_id_batch)
        ):
            bundle_status_by_id[requested_bundle_id] = bundle_status_entry

    landed_bundle_count = 0
    for bundle_id in all_bundle_ids:
        bundle_status_entry = bundle_status_by_id.get(bundle_id)
        landed = is_bundle_landed(bundle_status_entry)
        if landed:
            landed_bundle_count += 1
            status_text = bundle_status_entry["confirmation_status"]
        elif bundle_status_entry is not None:
            status_text = bundle_status_entry.get("confirmation_status") or "unknown"
        else:
            status_text = "not found"
        print(f"{bundle_id} landed={landed} status={status_text}")

    land_rate = landed_bundle_count / len(all_bundle_ids)
    print(f"{landed_bundle_count} of {len(all_bundle_ids)} landed, {land_rate:.2%}")


if __name__ == "__main__":
    main()
