# Remote Streaming

`datasift-diff` can stream data from S3 and GCS without downloading the
entire object into memory. This uses **HTTP Range requests** under the hood.

## How It Works

1. A HEAD request determines the object size.
2. The object is fetched in chunks of `chunk_size` bytes (default: 1 MiB).
3. Each chunk is passed to the format plugin.

For formats that support incremental parsing (JSON Lines), this means peak
memory is bounded by the chunk size. For formats that require the full
document (JSON array, Parquet), the chunks are concatenated before parsing.

## Python API

```python
from datasift_diff.io import iter_chunks

for chunk in iter_chunks("s3://bucket/huge.jsonl", chunk_size=4 * 1024 * 1024):
    process(chunk)
```

Or stream records directly:

```python
from datasift_diff.io import stream_records

for record in stream_records("s3://bucket/users.jsonl"):
    print(record)
```

## CLI

Streaming is automatic when the source is remote. The `--streaming` flag
controls a different optimization (merge-join for sorted inputs), not
remote fetching.

```bash
# Streams from S3 in 1 MiB chunks
datasift-diff s3://bucket/a.jsonl s3://bucket/b.jsonl --key id

# Streaming merge-join (requires sorted inputs)
datasift-diff s3://bucket/a-sorted.jsonl s3://bucket/b-sorted.jsonl --key id --streaming
```

## Chunk Size

The default chunk size is 1 MiB. For very large objects over fast networks,
increase it:

```python
from datasift_diff.uri import stream_uri

for chunk in stream_uri("s3://bucket/data.jsonl", chunk_size=8 * 1024 * 1024):
    ...
```

## Fallback Behavior

If a source plugin doesn't implement `stream_chunks()`, `stream_uri()`
falls back to a single-chunk yield of the full content. This is true for
`http://` and `https://` sources.

## Git Revisions

Git revisions are read with `git show`, which does not support Range
requests. The entire blob is read at once.

```bash
datasift-diff HEAD~1:data.jsonl HEAD:data.jsonl --key id
```