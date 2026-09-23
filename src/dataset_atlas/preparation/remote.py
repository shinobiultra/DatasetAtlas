"""Bounded concurrent source fingerprinting; source order remains canonical."""
from concurrent.futures import ThreadPoolExecutor

from dataset_atlas.storage.ranges import range_fingerprint


def pin_remote_files(files, hosts, check, update, workers=8):
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError('Remote fingerprint concurrency must be within 1..8')

    def pin(entry):
        check()
        return {**entry, 'etag': range_fingerprint(
            entry['url'], expected_size=entry['bytes'], allowed_hosts=hosts)}

    pinned = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # Submit only one bounded batch, so cancellation cannot leave thousands
        # of queued requests and exceptions cannot reorder source identities.
        for start in range(0, len(files), workers):
            check()
            futures = [pool.submit(pin, entry) for entry in files[start:start + workers]]
            try:
                for future in futures:
                    check()
                    entry = future.result()
                    pinned.append(entry)
                    update(stage='pinning remote shards', current_file=entry['source_name'],
                           pinned_shards=len(pinned), total_shards=len(files))
            except BaseException:
                for future in futures:
                    future.cancel()
                raise
    return pinned
