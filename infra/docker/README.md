# Docker images (API + worker)

## Shared uploads volume

Both `Dockerfile.api` and `Dockerfile.worker` set **`UPLOAD_ROOT=/data/uploads`**. Mount the **same** persistent volume at `/data/uploads` for the API and worker services so document uploads written by the API are visible to pipeline jobs (text extraction, certificate checks, video processing).

If `UPLOAD_ROOT` differs between processes or the working directory is used instead of `/data/uploads`, workers may raise `FileNotFoundError` when reading `storage_key` paths.

## Video / YouTube

Images install **ffmpeg** and **yt-dlp** so presentation video validation can download YouTube URLs and probe media. The worker image must include these tools if video units run there.

Quick verify after build:

```bash
docker run --rm invision-worker:latest /bin/sh -lc \
  'ffmpeg -version | head -n 1 && ffprobe -version | head -n 1 && yt-dlp --version'
```
