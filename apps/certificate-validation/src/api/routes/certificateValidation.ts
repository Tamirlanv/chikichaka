import { FastifyInstance } from "fastify";
import { z } from "zod";

import { validateCertificateImage } from "../../services/certificateValidationOrchestrator.js";

const DocumentTypeSchema = z.enum(["ielts", "toefl", "ent", "nis_12", "unknown"]);

const BodySchema = z
  .object({
    imagePath: z.string().min(1).optional(),
    imageBase64: z.string().min(1).optional(),
    mimeType: z.string().min(3).optional(),
    applicationId: z.string().uuid().optional(),
    includeSummary: z.boolean().optional(),
    plainText: z.string().optional(),
    expectedDocumentType: DocumentTypeSchema.optional(),
    englishProofKind: z.string().optional().nullable(),
    certificateProofKind: z.string().optional().nullable(),
    documentRole: z.enum(["english", "certificate", "additional"]).optional(),
    skipPersistence: z.boolean().optional(),
    ocrLang: z.string().min(1).optional()
  })
  .refine(
    (b) =>
      Boolean(b.plainText?.trim()) ||
      Boolean(b.imagePath?.trim()) ||
      Boolean(b.imageBase64?.trim()),
    { message: "Provide plainText, imagePath, or imageBase64" }
  );

export async function registerCertificateValidationRoutes(app: FastifyInstance): Promise<void> {
  app.get("/health", async (_request, reply) => reply.send({ status: "ok", service: "certificate-validation" }));

  app.post("/certificate-validation/validate", async (request, reply) => {
    const body = BodySchema.parse(request.body);
    const result = await validateCertificateImage({
      imagePath: body.imagePath,
      imageBase64: body.imageBase64,
      mimeType: body.mimeType,
      applicationId: body.applicationId,
      includeSummary: body.includeSummary,
      plainText: body.plainText,
      expectedDocumentType: body.expectedDocumentType ?? null,
      englishProofKind: body.englishProofKind,
      certificateProofKind: body.certificateProofKind,
      documentRole: body.documentRole,
      skipPersistence: body.skipPersistence,
      ocrLang: body.ocrLang ?? null
    });
    return reply.send(result);
  });
}
