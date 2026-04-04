import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";

const EXT: Record<string, string> = {
  "image/jpeg": ".jpg",
  "image/jpg": ".jpg",
  "image/png": ".png",
  "image/webp": ".webp",
  "image/heic": ".heic",
  "application/pdf": ".pdf"
};

export async function writeTempFileFromBase64(
  base64: string,
  mimeType: string
): Promise<{ path: string; cleanup: () => Promise<void> }> {
  const mt = (mimeType || "").split(";")[0].trim().toLowerCase();
  const ext = EXT[mt] ?? ".bin";
  const dir = await mkdtemp(join(tmpdir(), "cert-val-"));
  const path = join(dir, `upload${ext}`);
  const buf = Buffer.from(base64, "base64");
  await writeFile(path, buf);
  return {
    path,
    cleanup: async () => {
      await rm(dir, { recursive: true, force: true });
    }
  };
}
