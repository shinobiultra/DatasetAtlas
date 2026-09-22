# Running a workbench near the data

Install Dataset Atlas on a machine that has authorized access to the dataset and enough storage for the specific prepared source. Keep originals read-only. The workbench should bind to loopback by default and serve the same built frontend as the static site.

On the data machine, start the local service:

```bash
atlas serve
```

From your laptop, forward the service through SSH (replace the host and port if your local configuration differs):

```bash
ssh -N -L 8765:127.0.0.1:8765 user@research-host
```

Open `http://127.0.0.1:8765/?mode=workbench` on the laptop. Check the workbench capability response before starting a query or computation. The public static site does not probe localhost or automatically connect to this service. If port 8765 is occupied locally, change the first port in `-L` and open that local port in the browser.

The browser sees metadata and approved media returned by the workbench; raw storage paths stay on the data machine. Configure dataset roots and provider endpoints on that machine. Do not expose the service on a public interface, forward it to another user, or use a browser-side direct filesystem URL. Request approval for any bounded download, model transmission, or public export under the dataset's actual access and rights terms. An SSH tunnel alone does not grant redistribution rights.

For shared mounts, let the workbench own mutable indexes and job state on its own storage. A mounted original may be read as a source, but concurrent writers should not mutate the same operational database. Use the preparation plan to see expected downloads, extraction, and storage before running it.

Complete-data queries can use an immutable Parquet snapshot built from a bounded record iterator. The builder requires the source's expected record count and refuses a short or extra iterator; callers must explicitly set `population_scope="complete"` only for a verified full split. Its default is `preview`. The reader accepts typed filters over registered fields and returns counts for that snapshot. Random and stratified sampling, and joins to separate result snapshots, currently return an explicit unsupported error on this path. Query cancellation calls the active DuckDB connection's `interrupt()` method; it does not cancel source preparation or downloads.
